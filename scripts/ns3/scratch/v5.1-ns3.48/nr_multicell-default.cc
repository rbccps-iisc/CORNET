/*
 * nr_multicell-default.cc (v5.1)
 *
 * Places gNBs and UEs from a catalogue layout.json. Realtime scheduler.
 * Wrap-around uses HexagonalWraparoundModel with the layout's site positions.
 * --blockage enables TR 38.901 Model A. Indoor runs enable building penetration.
 * Aerial channels (UMa-AV, UMi-AV, RMa-AV) replace only the path-loss model.
 */

#include "cornet_base.h"
#include "cornet_population.h"

#include "ns3/antenna-module.h"
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/hexagonal-wraparound-model.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/nr-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/realtime-simulator-impl.h"
#include "ns3/three-gpp-aerial-propagation-loss-model.h"

#include <cmath>
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
            if (!node)
            {
                continue;
            }
            Ptr<ConstantVelocityMobilityModel> model = node->GetObject<ConstantVelocityMobilityModel>();
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

std::string
TerrestrialScenario(const std::string& channel)
{
    if (channel.size() > 3 && channel.substr(channel.size() - 3) == "-AV")
    {
        return channel.substr(0, channel.size() - 3);
    }
    return channel;
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
    double gnbTxPower = 35.0;

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
    cmd.AddValue("indoor", "Enable outdoor-to-indoor building penetration", indoor);
    cmd.AddValue("wraparound", "Install hexagonal wrap-around on the layout sites", wraparound);
    cmd.AddValue("channelUpdateMs", "Channel and condition update period in ms", channelUpdateMs);
    cmd.AddValue("numNonSelfBlocking", "Model A NumNonselfBlocking override", numNonSelfBlocking);
    cmd.Parse(argc, argv);

    CornetLayout layout = LoadCornetLayout(layoutFile);
    if (layout.sites.empty())
    {
        NS_FATAL_ERROR("nr_multicell requires --layoutFile with at least one site");
    }
    blockage = blockage || layout.blockage;
    indoor = indoor || layout.indoor;
    wraparound = wraparound || layout.wraparound;
    if (layout.channelUpdateMs > 0.0)
    {
        channelUpdateMs = layout.channelUpdateMs;
    }
    if (layout.numNonSelfBlocking >= 0)
    {
        numNonSelfBlocking = layout.numNonSelfBlocking;
    }
    const int sectors = std::max(1, layout.sectors);
    const std::string channel = layout.channel;
    const std::string scenario = TerrestrialScenario(channel);
    const bool aerial = channel.size() > 3 && channel.substr(channel.size() - 3) == "-AV";

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(layout.seed);
    if (realtime)
    {
        GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    }
    Config::SetDefault("ns3::ThreeGppChannelModel::UpdatePeriod", TimeValue(MilliSeconds(channelUpdateMs)));
    Config::SetDefault("ns3::ThreeGppChannelConditionModel::UpdatePeriod", TimeValue(MilliSeconds(channelUpdateMs)));
    Config::SetDefault("ns3::ThreeGppChannelModel::Blockage", BooleanValue(blockage));
    if (numNonSelfBlocking >= 0)
    {
        Config::SetDefault("ns3::ThreeGppChannelModel::NumNonselfBlocking", IntegerValue(numNonSelfBlocking));
    }

    NodeContainer gnbs;
    NodeContainer robots;
    NodeContainer background;
    gnbs.Create(layout.sites.size() * static_cast<uint32_t>(sectors));
    if (!layout.robots.empty())
    {
        robots.Create(layout.robots.size());
    }
    const uint32_t bgCount = static_cast<uint32_t>(std::max(0, layout.backgroundUesPerCell)) * layout.sites.size();
    if (bgCount > 0)
    {
        background.Create(bgCount);
    }

    MobilityHelper gnbMobility;
    gnbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    gnbMobility.Install(gnbs);
    for (uint32_t site = 0; site < layout.sites.size(); ++site)
    {
        for (int sector = 0; sector < sectors; ++sector)
        {
            const uint32_t index = site * sectors + static_cast<uint32_t>(sector);
            Ptr<MobilityModel> model = gnbs.Get(index)->GetObject<MobilityModel>();
            model->SetPosition(Vector(layout.sites[site].x, layout.sites[site].y, layout.sites[site].z));
            Names::Add(layout.sites[site].name + (sectors > 1 ? "-s" + std::to_string(sector) : ""), gnbs.Get(index));
        }
    }

    MobilityHelper robotMobility;
    robotMobility.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    robotMobility.Install(robots);
    for (uint32_t i = 0; i < robots.GetN(); ++i)
    {
        robots.Get(i)->GetObject<MobilityModel>()->SetPosition(
            Vector(layout.robots[i].x, layout.robots[i].y, layout.robots[i].z));
        if (!layout.robots[i].name.empty())
        {
            Names::Add(layout.robots[i].name, robots.Get(i));
        }
    }

    Ptr<UniformRandomVariable> jitter = CreateObject<UniformRandomVariable>();
    jitter->SetAttribute("Min", DoubleValue(-10.0));
    jitter->SetAttribute("Max", DoubleValue(10.0));
    jitter->SetStream(static_cast<int64_t>(layout.seed));
    MobilityHelper bgMobility;
    bgMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    bgMobility.Install(background);
    uint32_t bgIndex = 0;
    for (uint32_t site = 0; site < layout.sites.size() && bgIndex < background.GetN(); ++site)
    {
        for (int n = 0; n < layout.backgroundUesPerCell && bgIndex < background.GetN(); ++n, ++bgIndex)
        {
            background.Get(bgIndex)->GetObject<MobilityModel>()->SetPosition(
                Vector(layout.sites[site].x + jitter->GetValue(),
                       layout.sites[site].y + jitter->GetValue(),
                       1.5));
            Names::Add("bg" + std::to_string(bgIndex), background.Get(bgIndex));
        }
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

    Ptr<NrPointToPointEpcHelper> epc = CreateObject<NrPointToPointEpcHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();
    nrHelper->SetEpcHelper(epc);
    Ptr<IdealBeamformingHelper> beam = CreateObject<IdealBeamformingHelper>();
    beam->SetAttribute("BeamformingMethod", TypeIdValue(DirectPathBeamforming::GetTypeId()));
    nrHelper->SetBeamformingHelper(beam);
    nrHelper->SetSchedulerTypeId(TypeId::LookupByName("ns3::NrMacSchedulerOfdmaRR"));
    nrHelper->SetGnbPhyAttribute("Numerology", UintegerValue(numerology));
    nrHelper->SetGnbPhyAttribute("TxPower", DoubleValue(gnbTxPower));
    nrHelper->SetUePhyAttribute("TxPower", DoubleValue(txPower));

    Ptr<NrChannelHelper> channelHelper = CreateObject<NrChannelHelper>();
    channelHelper->ConfigureFactories(scenario, "Default", "ThreeGpp");
    channelHelper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(false));
    channelHelper->SetChannelConditionModelAttribute("UpdatePeriod", TimeValue(MilliSeconds(channelUpdateMs)));
    if (aerial)
    {
        std::cout << "caveat: aerial path loss only scenario=" << channel << "\n";
        channelHelper->ConfigurePropagationFactory(ThreeGppAerialPropagationLossModel::GetTypeId());
        channelHelper->SetPathlossAttribute("Scenario", StringValue(channel));
    }
    else if (indoor)
    {
        channelHelper->SetPathlossAttribute("BuildingPenetrationLossesEnabled", BooleanValue(true));
    }
    if (wraparound)
    {
        if (layout.sites.size() != 1 && layout.sites.size() != 7 && layout.sites.size() != 19)
        {
            NS_FATAL_ERROR("hex_wraparound supports 1, 7, or 19 sites, got " << layout.sites.size());
        }
        double isd = layout.isdM;
        if (isd <= 0.0 && layout.sites.size() > 1)
        {
            const double dx = layout.sites[1].x - layout.sites[0].x;
            const double dy = layout.sites[1].y - layout.sites[0].y;
            isd = std::sqrt(dx * dx + dy * dy);
        }
        if (isd <= 0.0)
        {
            NS_FATAL_ERROR("hex_wraparound requires a positive ISD");
        }
        Ptr<HexagonalWraparoundModel> wrap = CreateObject<HexagonalWraparoundModel>(isd, layout.sites.size());
        std::vector<Vector3D> positions;
        for (const auto& site : layout.sites)
        {
            positions.emplace_back(site.x, site.y, site.z);
        }
        wrap->SetSitePositions(positions);
        channelHelper->SetWraparoundModel(wrap);
    }

    CcBwpCreator creator;
    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequency, bandwidth, 1);
    OperationBandInfo band = creator.CreateOperationBandContiguousCc(bandConf);
    channelHelper->AssignChannelsToBands({band});
    BandwidthPartInfoPtrVector allBwps = CcBwpCreator::GetAllBwps({band});

    NetDeviceContainer gnbDevs = nrHelper->InstallGnbDevice(gnbs, allBwps);
    NetDeviceContainer ueDevs = nrHelper->InstallUeDevice(ues, allBwps);

    Ptr<Node> remoteHost = CreateObject<Node>();
    NodeContainer remote;
    remote.Add(remoteHost);
    InternetStackHelper internet;
    internet.Install(remote);
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2p.SetChannelAttribute("Delay", TimeValue(Seconds(0.0)));
    NetDeviceContainer inetDevs = p2p.Install(epc->GetPgwNode(), remoteHost);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("1.0.0.0", "255.0.0.0");
    ipv4.Assign(inetDevs);
    Ipv4StaticRoutingHelper routing;
    routing.GetStaticRouting(remoteHost->GetObject<Ipv4>())->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);
    internet.Install(ues);
    Ipv4InterfaceContainer ueIfaces = epc->AssignUeIpv4Address(ueDevs);
    for (uint32_t i = 0; i < ues.GetN(); ++i)
    {
        routing.GetStaticRouting(ues.Get(i)->GetObject<Ipv4>())->SetDefaultRoute(epc->GetUeDefaultGatewayAddress(), 1);
    }
    nrHelper->AttachToClosestGnb(ueDevs, gnbDevs);

    const uint16_t port = 1234;
    UdpServerHelper sink(port);
    ApplicationContainer servers = sink.Install(ues);
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
