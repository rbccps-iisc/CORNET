/*
 * wifi_basic-default.cc
 *
 * NS-3 WiFi (802.11ax) plus TapBridge. Access points follow layout.json sites.
 * Without a layout, --tgax selects a spacing from IEEE 802.11-14/0980r16:
 *   residential        10 m x 10 m x 3 m apartments (one floor of the 5-floor building)
 *   enterprise         inter-AP distance in the documented 10-20 m range (20 m used)
 *   indoor_small_bss   inter-AP distance in the documented 10-20 m range (20 m used)
 *   outdoor_large_bss  inter-AP distance in the documented 100-200 m range (150 m used)
 */

#include "cornet_base.h"

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/realtime-simulator-impl.h"
#include "ns3/tap-bridge-module.h"
#include "ns3/wifi-module.h"

#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

namespace
{

struct TGaxPreset
{
    const char* name;
    double spacingM;
    const char* note;
};

const TGaxPreset kPresets[] = {
    {"residential", 10.0, "IEEE 802.11-14/0980r16 apartment 10 m x 10 m x 3 m"},
    {"enterprise", 20.0, "IEEE 802.11-14/0980r16 enterprise inter-AP distance 10-20 m"},
    {"indoor_small_bss", 20.0, "IEEE 802.11-14/0980r16 indoor small BSS inter-AP distance 10-20 m"},
    {"outdoor_large_bss", 150.0, "IEEE 802.11-14/0980r16 outdoor large BSS inter-AP distance 100-200 m"},
};

void
InstallWifiProfile(Ptr<Node> from, Ipv4Address dest, const std::string& profile)
{
    const std::string use = profile.empty() ? "periodic_iot" : profile;
    if (use == "ftp" || use == "full_buffer")
    {
        BulkSendHelper bulk("ns3::UdpSocketFactory", InetSocketAddress(dest, 9));
        bulk.SetAttribute("MaxBytes", UintegerValue(0));
        bulk.SetAttribute("SendSize", UintegerValue(use == "full_buffer" ? 1400 : 512));
        bulk.Install(from).Start(Seconds(0.1));
        return;
    }
    std::string rate = "1Mbps";
    if (use == "video" || use == "xr")
    {
        rate = "5Mbps";
    }
    else if (use == "voip")
    {
        rate = "64kbps";
    }
    else if (use == "periodic_iot")
    {
        rate = "1kbps";
    }
    OnOffHelper onoff("ns3::UdpSocketFactory", InetSocketAddress(dest, 9));
    onoff.SetAttribute("DataRate", DataRateValue(DataRate(rate)));
    onoff.SetAttribute("PacketSize", UintegerValue(use == "periodic_iot" ? 64 : 512));
    onoff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1]"));
    onoff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0]"));
    onoff.Install(from).Start(Seconds(0.1));
}

const TGaxPreset*
FindPreset(const std::string& name)
{
    for (const auto& preset : kPresets)
    {
        if (name == preset.name)
        {
            return &preset;
        }
    }
    return nullptr;
}

void
WriteTimingSample(std::string path, double periodMs)
{
    double lagMs = 0.0;
    Ptr<RealtimeSimulatorImpl> rt = DynamicCast<RealtimeSimulatorImpl>(Simulator::GetImplementation());
    if (rt)
    {
        lagMs = (rt->RealtimeNow() - Simulator::Now()).GetSeconds() * 1000.0;
    }
    std::ofstream out(path.c_str(), std::ios::app);
    out << Simulator::Now().GetSeconds() << "," << lagMs << "\n";
    Simulator::Schedule(MilliSeconds(periodMs), &WriteTimingSample, path, periodMs);
}

void
ApplyMotion(CornetPositionFeed* feed)
{
    if (feed != nullptr)
    {
        for (const auto& sample : feed->Poll())
        {
            Ptr<Node> node = Names::Find<Node>(sample.name);
            Ptr<ConstantVelocityMobilityModel> model =
                node ? node->GetObject<ConstantVelocityMobilityModel>() : nullptr;
            if (!model)
            {
                continue;
            }
            model->SetPosition(Vector(sample.x, sample.y, sample.z));
            if (sample.hasVelocity)
            {
                model->SetVelocity(Vector(sample.vx, sample.vy, sample.vz));
            }
        }
    }
    Simulator::Schedule(MilliSeconds(100), &ApplyMotion, feed);
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string layoutFile;
    std::string positionsSocket;
    std::string timingLog;
    std::string aoiStats;
    std::string tgax = "indoor_small_bss";
    double timingPeriodMs = 10.0;
    double simTime = 5.0;
    bool realtime = true;

    CommandLine cmd;
    cmd.AddValue("layoutFile", "Catalogue layout.json", layoutFile);
    cmd.AddValue("positionsSocket", "Unix socket of position updates", positionsSocket);
    cmd.AddValue("timingLog", "Append sim_s,lag_ms samples", timingLog);
    cmd.AddValue("timingPeriodMs", "Timing sample period in milliseconds", timingPeriodMs);
    cmd.AddValue("aoiStats", "Accepted for the plugin; this program does not write it", aoiStats);
    cmd.AddValue("tgax", "residential, enterprise, indoor_small_bss, or outdoor_large_bss", tgax);
    cmd.AddValue("simTime", "Simulated seconds", simTime);
    cmd.AddValue("realtime", "Use the realtime scheduler", realtime);
    cmd.Parse(argc, argv);

    const TGaxPreset* preset = FindPreset(tgax);
    if (preset == nullptr)
    {
        NS_FATAL_ERROR("unknown TGax preset '" << tgax << "'");
    }
    std::cout << "tgax preset=" << preset->name << " spacing_m=" << preset->spacingM << " (" << preset->note << ")\n";

    CornetLayout layout = LoadCornetLayout(layoutFile);
    std::vector<Vector> apPositions;
    std::vector<std::string> staNames;
    std::vector<Vector> staPositions;
    if (!layout.sites.empty())
    {
        for (const auto& site : layout.sites)
        {
            apPositions.emplace_back(site.x, site.y, site.z);
        }
        for (const auto& robot : layout.robots)
        {
            staNames.push_back(robot.name);
            staPositions.emplace_back(robot.x, robot.y, robot.z);
        }
        for (const auto& device : layout.devices)
        {
            if (device.kind == "wifi_neighbour")
            {
                continue;
            }
            staNames.push_back(device.name);
            staPositions.emplace_back(device.x, device.y, device.z);
        }
    }
    else if (std::string(preset->name) == "residential")
    {
        for (int i = 0; i < 4; ++i)
        {
            apPositions.emplace_back((i % 2) * 10.0, (i / 2) * 10.0, 1.5);
        }
    }
    else
    {
        apPositions.emplace_back(0.0, 0.0, 3.0);
        apPositions.emplace_back(preset->spacingM, 0.0, 3.0);
    }
    if (staPositions.empty())
    {
        staNames.push_back("sta0");
        staPositions.emplace_back(1.0, 1.0, 1.5);
    }
    uint32_t primaryStaCount = static_cast<uint32_t>(staNames.size());
    if (!layout.sites.empty() && !(layout.robots.empty() && layout.devices.empty()))
    {
        primaryStaCount = static_cast<uint32_t>(layout.robots.size());
    }

    if (realtime)
    {
        GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    }

    NodeContainer aps;
    NodeContainer stas;
    aps.Create(apPositions.size());
    stas.Create(staPositions.size());
    MobilityHelper still;
    still.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    still.Install(aps);
    MobilityHelper moving;
    moving.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    moving.Install(stas);
    for (uint32_t i = 0; i < aps.GetN(); ++i)
    {
        aps.Get(i)->GetObject<MobilityModel>()->SetPosition(apPositions[i]);
    }
    for (uint32_t i = 0; i < stas.GetN(); ++i)
    {
        stas.Get(i)->GetObject<MobilityModel>()->SetPosition(staPositions[i]);
        if (!staNames[i].empty())
        {
            Names::Add(staNames[i], stas.Get(i));
        }
    }

    YansWifiChannelHelper channelHelper = YansWifiChannelHelper::Default();
    Ptr<YansWifiChannel> sharedChannel = channelHelper.Create();
    YansWifiPhyHelper phy;
    phy.SetChannel(sharedChannel);
    std::ostringstream channelSettings;
    channelSettings << "{" << layout.wifiChannel << ", 20, BAND_5GHZ, 0}";
    phy.Set("ChannelSettings", StringValue(channelSettings.str()));
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211ax);
    wifi.SetRemoteStationManager("ns3::IdealWifiManager");
    WifiMacHelper mac;
    Ssid ssid = Ssid("cornet");
    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDevs = wifi.Install(phy, mac, aps);
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer staDevs = wifi.Install(phy, mac, stas);

    InternetStackHelper internet;
    internet.Install(aps);
    internet.Install(stas);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer apIfaces = ipv4.Assign(apDevs);
    Ipv4InterfaceContainer staIfaces = ipv4.Assign(staDevs);

    const CornetArgs cornet = ParseCornetArgs(argc, argv);
    TapBridgeHelper tap;
    tap.SetAttribute("Mode", StringValue("UseLocal"));
    for (uint32_t i = 0; i < cornet.tuns.size() && i < stas.GetN(); ++i)
    {
        tap.SetAttribute("DeviceName", StringValue(cornet.tuns[i].first));
        tap.Install(stas.Get(i), staDevs.Get(i));
    }

    const uint16_t port = 1234;
    ApplicationContainer servers = UdpServerHelper(port).Install(stas);
    UdpClientHelper client;
    client.SetAttribute("MaxPackets", UintegerValue(0xffffffff));
    client.SetAttribute("Interval", TimeValue(MilliSeconds(10)));
    client.SetAttribute("PacketSize", UintegerValue(64));
    client.SetAttribute("RemotePort", UintegerValue(port));
    ApplicationContainer clients;
    for (uint32_t i = 0; i < primaryStaCount; ++i)
    {
        client.SetAttribute("RemoteAddress", AddressValue(staIfaces.GetAddress(i)));
        clients.Add(client.Install(aps.Get(0)));
    }
    servers.Start(Seconds(0.1));
    clients.Start(Seconds(0.1));
    if (stas.GetN() > primaryStaCount)
    {
        NodeContainer populationStas;
        uint32_t cursor = 0;
        for (const auto& device : layout.devices)
        {
            if (device.kind == "wifi_neighbour")
            {
                continue;
            }
            populationStas.Add(stas.Get(primaryStaCount + cursor));
            InstallWifiProfile(aps.Get(0), staIfaces.GetAddress(primaryStaCount + cursor), device.traffic);
            ++cursor;
        }
        UdpServerHelper(9).Install(populationStas).Start(Seconds(0.1));
    }
    for (const auto& device : layout.devices)
    {
        if (device.kind != "wifi_neighbour")
        {
            continue;
        }
        NodeContainer nap;
        NodeContainer nsta;
        nap.Create(1);
        nsta.Create(1);
        MobilityHelper neighbourMobility;
        neighbourMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        neighbourMobility.Install(nap);
        neighbourMobility.Install(nsta);
        nap.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(device.x, device.y, device.z));
        nsta.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(device.x + 1.0, device.y, 1.5));
        const int neighbourChannel = device.channel < 0 ? layout.wifiChannel : device.channel;
        YansWifiPhyHelper neighbourPhy;
        if (neighbourChannel == layout.wifiChannel)
        {
            neighbourPhy.SetChannel(sharedChannel);
        }
        else
        {
            neighbourPhy.SetChannel(YansWifiChannelHelper::Default().Create());
        }
        std::ostringstream neighbourSettings;
        neighbourSettings << "{" << neighbourChannel << ", 20, BAND_5GHZ, 0}";
        neighbourPhy.Set("ChannelSettings", StringValue(neighbourSettings.str()));
        WifiMacHelper neighbourMac;
        Ssid neighbourSsid(device.name);
        neighbourMac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(neighbourSsid));
        NetDeviceContainer neighbourApDev = wifi.Install(neighbourPhy, neighbourMac, nap);
        neighbourMac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(neighbourSsid), "ActiveProbing", BooleanValue(false));
        NetDeviceContainer neighbourStaDev = wifi.Install(neighbourPhy, neighbourMac, nsta);
        internet.Install(nap);
        internet.Install(nsta);
        ipv4.NewNetwork();
        Ipv4InterfaceContainer neighbourApIf = ipv4.Assign(neighbourApDev);
        ipv4.Assign(neighbourStaDev);
        UdpServerHelper(9).Install(nap).Start(Seconds(0.1));
        InstallWifiProfile(nsta.Get(0), neighbourApIf.GetAddress(0), device.traffic);
    }

    CornetPositionFeed feed;
    feed.Start(positionsSocket);
    Simulator::Schedule(MilliSeconds(100), &ApplyMotion, &feed);
    if (!timingLog.empty() && timingPeriodMs > 0.0)
    {
        Simulator::Schedule(MilliSeconds(timingPeriodMs), &WriteTimingSample, timingLog, timingPeriodMs);
    }
    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    feed.Stop();
    Simulator::Destroy();
    return 0;
}
