/*
 * nr_multicell-default.cc (v2.4 subset)
 *
 * Reads layout.json and places gNBs and UEs. Realtime scheduler.
 * hex_wraparound, InF, and TR 36.777 aerial channels are not on this lane.
 */

#include "cornet_base.h"
#include "cornet_population.h"

#include "ns3/antenna-module.h"
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/nr-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/realtime-simulator-impl.h"

#include <fstream>
#include <iostream>
#include <string>

using namespace ns3;

namespace
{

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

BandwidthPartInfo::Scenario
BandScenario(const std::string& channel)
{
    if (channel == "UMi")
    {
        return BandwidthPartInfo::UMi_StreetCanyon;
    }
    if (channel == "RMa")
    {
        return BandwidthPartInfo::RMa;
    }
    if (channel == "InH")
    {
        return BandwidthPartInfo::InH_OfficeMixed;
    }
    if (channel == "UMa" || channel.empty())
    {
        return BandwidthPartInfo::UMa;
    }
    NS_FATAL_ERROR("v2.4-ns3.38 nr_multicell does not provide channel '"
                   << channel << "' (InF needs channel_inf; aerial needs channel_aerial_36777)");
    return BandwidthPartInfo::UMa;
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string layoutFile;
    std::string positionsSocket;
    std::string timingLog;
    std::string aoiStats;
    double timingPeriodMs = 10.0;
    double simTime = 5.0;
    uint16_t numerology = 1;
    bool realtime = true;
    bool blockage = false;
    bool indoor = false;
    bool wraparound = false;
    double channelUpdateMs = 100.0;
    int numNonSelfBlocking = -1;
    double centralFrequency = 3.5e9;
    double bandwidth = 100e6;
    double txPower = 23.0;

    CommandLine cmd;
    cmd.AddValue("layoutFile", "Catalogue layout.json", layoutFile);
    cmd.AddValue("positionsSocket", "Unix socket of position updates", positionsSocket);
    cmd.AddValue("timingLog", "Append sim_s,lag_ms samples", timingLog);
    cmd.AddValue("timingPeriodMs", "Timing sample period in milliseconds", timingPeriodMs);
    cmd.AddValue("aoiStats", "Accepted for the plugin; this program does not write it", aoiStats);
    cmd.AddValue("simTime", "Simulated seconds", simTime);
    cmd.AddValue("numerology", "NR numerology", numerology);
    cmd.AddValue("realtime", "Use the realtime scheduler", realtime);
    cmd.AddValue("blockage", "Enable TR 38.901 Model A", blockage);
    cmd.AddValue("indoor", "Select a buildings propagation scenario", indoor);
    cmd.AddValue("wraparound", "Rejected on this lane", wraparound);
    cmd.AddValue("channelUpdateMs", "Channel and condition update period in ms", channelUpdateMs);
    cmd.AddValue("numNonSelfBlocking", "Model A NumNonselfBlocking override", numNonSelfBlocking);
    cmd.Parse(argc, argv);

    CornetLayout layout = LoadCornetLayout(layoutFile);
    if (layout.sites.empty())
    {
        NS_FATAL_ERROR("nr_multicell requires --layoutFile with at least one site");
    }
    if (wraparound || layout.wraparound)
    {
        NS_FATAL_ERROR("hex_wraparound is not available on v2.4-ns3.38");
    }
    blockage = blockage || layout.blockage;
    indoor = indoor || layout.indoor;
    if (layout.channelUpdateMs > 0.0)
    {
        channelUpdateMs = layout.channelUpdateMs;
    }

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(layout.seed);
    if (realtime)
    {
        GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    }
    Config::SetDefault("ns3::ThreeGppChannelModel::UpdatePeriod", TimeValue(MilliSeconds(channelUpdateMs)));
    Config::SetDefault("ns3::ThreeGppChannelModel::Blockage", BooleanValue(blockage));
    if (numNonSelfBlocking >= 0 || layout.numNonSelfBlocking >= 0)
    {
        const int count = numNonSelfBlocking >= 0 ? numNonSelfBlocking : layout.numNonSelfBlocking;
        Config::SetDefault("ns3::ThreeGppChannelModel::NumNonselfBlocking", IntegerValue(count));
    }

    const int sectors = std::max(1, layout.sectors);
    NodeContainer gnbs;
    NodeContainer robots;
    gnbs.Create(layout.sites.size() * static_cast<uint32_t>(sectors));
    if (!layout.robots.empty())
    {
        robots.Create(layout.robots.size());
    }
    const uint32_t bgCount =
        static_cast<uint32_t>(std::max(0, layout.backgroundUesPerCell)) * layout.sites.size();
    NodeContainer background;
    if (bgCount > 0)
    {
        background.Create(bgCount);
    }

    MobilityHelper still;
    still.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    still.Install(gnbs);
    still.Install(background);
    MobilityHelper moving;
    moving.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    moving.Install(robots);
    for (uint32_t site = 0; site < layout.sites.size(); ++site)
    {
        for (int sector = 0; sector < sectors; ++sector)
        {
            const uint32_t index = site * sectors + static_cast<uint32_t>(sector);
            gnbs.Get(index)->GetObject<MobilityModel>()->SetPosition(
                Vector(layout.sites[site].x, layout.sites[site].y, layout.sites[site].z));
        }
    }
    for (uint32_t i = 0; i < robots.GetN(); ++i)
    {
        robots.Get(i)->GetObject<MobilityModel>()->SetPosition(
            Vector(layout.robots[i].x, layout.robots[i].y, layout.robots[i].z));
        if (!layout.robots[i].name.empty())
        {
            Names::Add(layout.robots[i].name, robots.Get(i));
        }
    }
    for (uint32_t i = 0; i < background.GetN(); ++i)
    {
        const auto& site = layout.sites[i % layout.sites.size()];
        background.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(site.x + 5.0, site.y, 1.5));
    }

    NodeContainer ues;
    ues.Add(robots);
    ues.Add(background);
    std::vector<std::string> populationTraffic;
    AddCornetPopulation(layout, ues, populationTraffic);
    if (ues.GetN() == 0)
    {
        NS_FATAL_ERROR("nr_multicell needs a robot or a background UE");
    }

    auto scenario = BandScenario(layout.channel);
    if (indoor && layout.channel == "UMa")
    {
        scenario = BandwidthPartInfo::UMa_Buildings;
    }
    else if (indoor && layout.channel == "UMi")
    {
        scenario = BandwidthPartInfo::UMi_Buildings;
    }

    Ptr<NrPointToPointEpcHelper> epc = CreateObject<NrPointToPointEpcHelper>();
    Ptr<IdealBeamformingHelper> beam = CreateObject<IdealBeamformingHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();
    nrHelper->SetBeamformingHelper(beam);
    nrHelper->SetEpcHelper(epc);
    nrHelper->SetSchedulerTypeId(TypeId::LookupByName("ns3::NrMacSchedulerOfdmaRR"));
    Time update = MilliSeconds(channelUpdateMs);
    nrHelper->SetChannelConditionModelAttribute("UpdatePeriod", TimeValue(update));
    nrHelper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(false));

    CcBwpCreator creator;
    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequency, bandwidth, 1, scenario);
    OperationBandInfo band = creator.CreateOperationBandContiguousCc(bandConf);
    nrHelper->InitializeOperationBand(&band);
    BandwidthPartInfoPtrVector allBwps = CcBwpCreator::GetAllBwps({band});
    NetDeviceContainer gnbDevs = nrHelper->InstallGnbDevice(gnbs, allBwps);
    NetDeviceContainer ueDevs = nrHelper->InstallUeDevice(ues, allBwps);
    for (uint32_t i = 0; i < gnbDevs.GetN(); ++i)
    {
        nrHelper->GetGnbPhy(gnbDevs.Get(i), 0)->SetAttribute("Numerology", UintegerValue(numerology));
        nrHelper->GetGnbPhy(gnbDevs.Get(i), 0)->SetAttribute("TxPower", DoubleValue(txPower));
        DynamicCast<NrGnbNetDevice>(gnbDevs.Get(i))->UpdateConfig();
    }
    for (uint32_t i = 0; i < ueDevs.GetN(); ++i)
    {
        DynamicCast<NrUeNetDevice>(ueDevs.Get(i))->UpdateConfig();
    }

    Ptr<Node> remoteHost = CreateObject<Node>();
    InternetStackHelper internet;
    internet.Install(remoteHost);
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2p.SetChannelAttribute("Delay", TimeValue(Seconds(0.0)));
    NetDeviceContainer inetDevs = p2p.Install(epc->GetPgwNode(), remoteHost);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("1.0.0.0", "255.0.0.0");
    ipv4.Assign(inetDevs);
    Ipv4StaticRoutingHelper routing;
    routing.GetStaticRouting(remoteHost->GetObject<Ipv4>())
        ->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);
    internet.Install(ues);
    Ipv4InterfaceContainer ueIfaces = epc->AssignUeIpv4Address(ueDevs);
    for (uint32_t i = 0; i < ues.GetN(); ++i)
    {
        routing.GetStaticRouting(ues.Get(i)->GetObject<Ipv4>())->SetDefaultRoute(epc->GetUeDefaultGatewayAddress(), 1);
    }
    nrHelper->AttachToClosestEnb(ueDevs, gnbDevs);

    const uint16_t port = 1234;
    ApplicationContainer servers = UdpServerHelper(port).Install(ues);
    UdpClientHelper client;
    client.SetAttribute("MaxPackets", UintegerValue(0xffffffff));
    client.SetAttribute("Interval", TimeValue(MilliSeconds(10)));
    client.SetAttribute("PacketSize", UintegerValue(64));
    client.SetAttribute("RemotePort", UintegerValue(port));
    ApplicationContainer clients;
    const uint32_t cbrCount = ues.GetN() - populationTraffic.size();
    for (uint32_t i = 0; i < cbrCount; ++i)
    {
        client.SetAttribute("RemoteAddress", AddressValue(ueIfaces.GetAddress(i)));
        clients.Add(client.Install(remoteHost));
    }
    servers.Start(Seconds(0.1));
    clients.Start(Seconds(0.1));
    if (!populationTraffic.empty())
    {
        NodeContainer profileNodes;
        for (uint32_t i = 0; i < populationTraffic.size(); ++i)
        {
            profileNodes.Add(ues.Get(cbrCount + i));
            InstallCornetProfile(remoteHost, ueIfaces.GetAddress(cbrCount + i), populationTraffic[i]);
        }
        UdpServerHelper(1235).Install(profileNodes).Start(Seconds(0.1));
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
