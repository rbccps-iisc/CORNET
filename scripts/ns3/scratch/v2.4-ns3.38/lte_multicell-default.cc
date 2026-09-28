/*
 * lte_multicell-default.cc
 *
 * LTE layout from catalogue layout.json. Handover is A3-RSRP.
 * Realtime scheduler. Position updates use constant-velocity mobility.
 */

#include "cornet_base.h"
#include "cornet_population.h"

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/lte-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/realtime-simulator-impl.h"

#include <fstream>
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
    bool realtime = true;

    CommandLine cmd;
    cmd.AddValue("layoutFile", "Catalogue layout.json", layoutFile);
    cmd.AddValue("positionsSocket", "Unix socket of position updates", positionsSocket);
    cmd.AddValue("timingLog", "Append sim_s,lag_ms samples", timingLog);
    cmd.AddValue("timingPeriodMs", "Timing sample period in milliseconds", timingPeriodMs);
    cmd.AddValue("aoiStats", "Accepted for the plugin; this program does not write it", aoiStats);
    cmd.AddValue("simTime", "Simulated seconds", simTime);
    cmd.AddValue("realtime", "Use the realtime scheduler", realtime);
    cmd.Parse(argc, argv);

    CornetLayout layout = LoadCornetLayout(layoutFile);
    if (layout.sites.empty())
    {
        NS_FATAL_ERROR("lte_multicell requires --layoutFile with at least one site");
    }
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(layout.seed);
    if (realtime)
    {
        GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    }

    NodeContainer gnbs;
    NodeContainer robots;
    gnbs.Create(layout.sites.size());
    if (!layout.robots.empty())
    {
        robots.Create(layout.robots.size());
    }
    NodeContainer background;
    const uint32_t bgCount =
        static_cast<uint32_t>(std::max(0, layout.backgroundUesPerCell)) * layout.sites.size();
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
    for (uint32_t i = 0; i < gnbs.GetN(); ++i)
    {
        gnbs.Get(i)->GetObject<MobilityModel>()->SetPosition(
            Vector(layout.sites[i].x, layout.sites[i].y, layout.sites[i].z));
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
        background.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(site.x + 8.0, site.y, 1.5));
    }
    NodeContainer ues;
    ues.Add(robots);
    ues.Add(background);
    std::vector<std::string> populationTraffic;
    AddCornetPopulation(layout, ues, populationTraffic);
    if (ues.GetN() == 0)
    {
        NS_FATAL_ERROR("lte_multicell needs a robot or a background UE");
    }

    Ptr<PointToPointEpcHelper> epc = CreateObject<PointToPointEpcHelper>();
    Ptr<LteHelper> lte = CreateObject<LteHelper>();
    lte->SetEpcHelper(epc);
    lte->SetSchedulerType("ns3::RrFfMacScheduler");
    lte->SetHandoverAlgorithmType("ns3::A3RsrpHandoverAlgorithm");
    lte->SetHandoverAlgorithmAttribute("Hysteresis", DoubleValue(3.0));
    lte->SetHandoverAlgorithmAttribute("TimeToTrigger", TimeValue(MilliSeconds(256)));
    NetDeviceContainer gnbDevs = lte->InstallEnbDevice(gnbs);
    InternetStackHelper internet;
    internet.Install(ues);
    NetDeviceContainer ueDevs = lte->InstallUeDevice(ues);
    Ipv4InterfaceContainer ueIfaces = epc->AssignUeIpv4Address(ueDevs);
    Ipv4StaticRoutingHelper routing;
    for (uint32_t i = 0; i < ues.GetN(); ++i)
    {
        routing.GetStaticRouting(ues.Get(i)->GetObject<Ipv4>())->SetDefaultRoute(epc->GetUeDefaultGatewayAddress(), 1);
    }
    lte->AttachToClosestEnb(ueDevs, gnbDevs);
    lte->AddX2Interface(gnbs);

    Ptr<Node> remoteHost = CreateObject<Node>();
    InternetStackHelper remoteStack;
    remoteStack.Install(remoteHost);
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2p.SetChannelAttribute("Delay", TimeValue(Seconds(0.010)));
    NetDeviceContainer inetDevs = p2p.Install(epc->GetPgwNode(), remoteHost);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("1.0.0.0", "255.0.0.0");
    ipv4.Assign(inetDevs);
    routing.GetStaticRouting(remoteHost->GetObject<Ipv4>())
        ->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);

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
