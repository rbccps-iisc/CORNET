/*
 * bench_nr_multicell-default.cc
 *
 * Standalone NR speed / realtime-lag benchmark for CORNET.
 * No TAP devices. Layouts come from HexagonalGridScenarioHelper.
 * v2.4 has no hexagonal wrap-around; --wraparound is accepted and ignored.
 *
 * Sites: 1 (0 rings), 7 (1 ring), 19 (3 rings). Sectors: 1 or 3.
 * uesPerCell=0 still creates one silent UE because the helper asserts ut > 0.
 */

#include "ns3/antenna-module.h"
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/nr-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/realtime-simulator-impl.h"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <string>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CornetBenchNrMulticell");

namespace
{

void
WriteTimingSample(std::string path, double periodMs)
{
    double lagMs = 0.0;
    Ptr<RealtimeSimulatorImpl> rt =
        DynamicCast<RealtimeSimulatorImpl>(Simulator::GetImplementation());
    if (rt)
    {
        lagMs = (rt->RealtimeNow() - Simulator::Now()).GetSeconds() * 1000.0;
    }
    std::ofstream out(path.c_str(), std::ios::app);
    out << Simulator::Now().GetSeconds() << "," << lagMs << "\n";
    Simulator::Schedule(MilliSeconds(periodMs), &WriteTimingSample, path, periodMs);
}

uint8_t
RingsForSites(uint32_t sites)
{
    if (sites == 1)
    {
        return 0;
    }
    if (sites == 7)
    {
        return 1;
    }
    if (sites == 19)
    {
        return 3;
    }
    NS_ABORT_MSG("sites must be 1, 7 or 19, got " << sites);
    return 0;
}

std::string
SchedulerTypeIdName(const std::string& name)
{
    if (name == "rr" || name == "ns3::NrMacSchedulerOfdmaRR")
    {
        return "ns3::NrMacSchedulerOfdmaRR";
    }
    if (name == "pf" || name == "ns3::NrMacSchedulerOfdmaPF")
    {
        return "ns3::NrMacSchedulerOfdmaPF";
    }
    if (name == "tdma_rr" || name == "ns3::NrMacSchedulerTdmaRR")
    {
        return "ns3::NrMacSchedulerTdmaRR";
    }
    NS_ABORT_MSG("unknown scheduler '" << name << "' (expected rr, pf or tdma_rr)");
    return "";
}

} // namespace

int
main(int argc, char* argv[])
{
    uint32_t sites = 1;
    uint32_t sectors = 3;
    uint32_t uesPerCell = 5;
    std::string traffic = "periodic";
    double channelUpdateMs = 100.0;
    uint16_t numerology = 1;
    bool wraparound = false;
    bool realtime = true;
    std::string scheduler = "rr";
    double simTime = 20.0;
    uint32_t rngRun = 1;
    std::string timingLog;
    double timingPeriodMs = 10.0;
    std::string outputDir = "/tmp";
    double centralFrequency = 3.5e9;
    double bandwidth = 100e6;
    double txPower = 23.0;

    CommandLine cmd;
    cmd.AddValue("sites", "Hexagonal sites: 1, 7 or 19", sites);
    cmd.AddValue("sectors", "Sectors per site: 1 or 3", sectors);
    cmd.AddValue("uesPerCell", "UEs per cell (0 creates one silent UE)", uesPerCell);
    cmd.AddValue("traffic", "periodic, full_buffer or both", traffic);
    cmd.AddValue("channelUpdateMs",
                 "ThreeGpp channel and condition update period in ms (0 = never)",
                 channelUpdateMs);
    cmd.AddValue("numerology", "NR numerology", numerology);
    cmd.AddValue("wraparound", "Request wrap-around (ignored on v2.4)", wraparound);
    cmd.AddValue("realtime",
                 "Use RealtimeSimulatorImpl when true; default scheduler when false",
                 realtime);
    cmd.AddValue("scheduler", "rr, pf or tdma_rr", scheduler);
    cmd.AddValue("simTime", "Simulated seconds", simTime);
    cmd.AddValue("rngRun", "NS-3 RNG run number", rngRun);
    cmd.AddValue("timingLog", "Append sim_s,lag_ms samples", timingLog);
    cmd.AddValue("timingPeriodMs", "Timing sample period in milliseconds", timingPeriodMs);
    cmd.AddValue("outputDir", "Directory for helper plot files", outputDir);
    cmd.Parse(argc, argv);

    if (sectors != 1 && sectors != 3)
    {
        NS_ABORT_MSG("sectors must be 1 or 3");
    }
    if (traffic != "periodic" && traffic != "full_buffer" && traffic != "both")
    {
        NS_ABORT_MSG("traffic must be periodic, full_buffer or both");
    }
    if (wraparound)
    {
        std::cerr << "bench_nr_multicell: --wraparound ignored; v2.4 has no hex_wraparound\n";
    }

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(rngRun);

    if (realtime)
    {
        GlobalValue::Bind("SimulatorImplementationType",
                          StringValue("ns3::RealtimeSimulatorImpl"));
    }
    GlobalValue::Bind("ChecksumEnabled", BooleanValue(true));
    Config::SetDefault("ns3::LteRlcUm::MaxTxBufferSize", UintegerValue(999999999));

    HexagonalGridScenarioHelper grid;
    grid.SetScenarioParameters("UMa");
    grid.SetSectorization(sectors);
    grid.SetNumRings(RingsForSites(sites));
    const uint32_t cells = grid.GetNumSites() * sectors;
    const uint32_t trafficUes = uesPerCell * cells;
    const uint32_t utCount = std::max<uint32_t>(1, trafficUes);
    if (uesPerCell == 0)
    {
        std::cerr << "bench_nr_multicell: uesPerCell=0; one silent UE created "
                     "(HexagonalGridScenarioHelper requires at least one UE)\n";
    }
    grid.SetUtNumber(utCount);
    grid.SetResultsDir(outputDir);
    grid.SetSimTag("cornet-bench");
    grid.AssignStreams(1);
    grid.CreateScenario();

    NodeContainer gnbs = grid.GetBaseStations();
    NodeContainer ues = grid.GetUserTerminals();
    std::cout << "CORNET_BENCH layout sites=" << grid.GetNumSites() << " cells=" << gnbs.GetN()
              << " ues=" << ues.GetN() << " trafficUes=" << trafficUes << "\n";

    Ptr<NrPointToPointEpcHelper> epcHelper = CreateObject<NrPointToPointEpcHelper>();
    Ptr<IdealBeamformingHelper> beamforming = CreateObject<IdealBeamformingHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();
    nrHelper->SetBeamformingHelper(beamforming);
    nrHelper->SetEpcHelper(epcHelper);
    nrHelper->SetSchedulerTypeId(TypeId::LookupByName(SchedulerTypeIdName(scheduler)));

    Time update = MilliSeconds(channelUpdateMs);
    Config::SetDefault("ns3::ThreeGppChannelModel::UpdatePeriod", TimeValue(update));
    nrHelper->SetChannelConditionModelAttribute("UpdatePeriod", TimeValue(update));
    nrHelper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(false));

    CcBwpCreator creator;
    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequency,
                                                   bandwidth,
                                                   1,
                                                   BandwidthPartInfo::UMa);
    OperationBandInfo band = creator.CreateOperationBandContiguousCc(bandConf);
    nrHelper->InitializeOperationBand(&band);
    BandwidthPartInfoPtrVector allBwps = CcBwpCreator::GetAllBwps({band});

    beamforming->SetAttribute("BeamformingMethod",
                              TypeIdValue(DirectPathBeamforming::GetTypeId()));
    epcHelper->SetAttribute("S1uLinkDelay", TimeValue(MilliSeconds(0)));
    nrHelper->SetUeAntennaAttribute("NumRows", UintegerValue(2));
    nrHelper->SetUeAntennaAttribute("NumColumns", UintegerValue(4));
    nrHelper->SetUeAntennaAttribute("AntennaElement",
                                    PointerValue(CreateObject<IsotropicAntennaModel>()));
    nrHelper->SetGnbAntennaAttribute("NumRows", UintegerValue(4));
    nrHelper->SetGnbAntennaAttribute("NumColumns", UintegerValue(8));
    nrHelper->SetGnbAntennaAttribute("AntennaElement",
                                     PointerValue(CreateObject<IsotropicAntennaModel>()));
    nrHelper->SetGnbBwpManagerAlgorithmAttribute("NGBR_LOW_LAT_EMBB", UintegerValue(0));
    nrHelper->SetUeBwpManagerAlgorithmAttribute("NGBR_LOW_LAT_EMBB", UintegerValue(0));

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

    Ptr<Node> pgw = epcHelper->GetPgwNode();
    NodeContainer remoteHostContainer;
    remoteHostContainer.Create(1);
    Ptr<Node> remoteHost = remoteHostContainer.Get(0);
    InternetStackHelper internet;
    internet.Install(remoteHostContainer);
    PointToPointHelper p2ph;
    p2ph.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2ph.SetDeviceAttribute("Mtu", UintegerValue(2500));
    p2ph.SetChannelAttribute("Delay", TimeValue(Seconds(0.0)));
    NetDeviceContainer internetDevices = p2ph.Install(pgw, remoteHost);
    Ipv4AddressHelper ipv4h;
    ipv4h.SetBase("1.0.0.0", "255.0.0.0");
    ipv4h.Assign(internetDevices);
    Ipv4StaticRoutingHelper ipv4RoutingHelper;
    Ptr<Ipv4StaticRouting> remoteHostStaticRouting =
        ipv4RoutingHelper.GetStaticRouting(remoteHost->GetObject<Ipv4>());
    remoteHostStaticRouting->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);
    internet.Install(ues);
    Ipv4InterfaceContainer ueIfaces = epcHelper->AssignUeIpv4Address(ueDevs);
    for (uint32_t j = 0; j < ues.GetN(); ++j)
    {
        Ptr<Ipv4StaticRouting> ueStaticRouting =
            ipv4RoutingHelper.GetStaticRouting(ues.Get(j)->GetObject<Ipv4>());
        ueStaticRouting->SetDefaultRoute(epcHelper->GetUeDefaultGatewayAddress(), 1);
    }
    nrHelper->AttachToClosestEnb(ueDevs, gnbDevs);

    const bool wantPeriodic = traffic == "periodic" || traffic == "both";
    const bool wantFull = traffic == "full_buffer" || traffic == "both";
    const uint16_t portPeriodic = 1234;
    const uint16_t portFull = 1235;
    ApplicationContainer servers;
    ApplicationContainer clients;
    if (trafficUes > 0 && wantPeriodic)
    {
        UdpServerHelper sink(portPeriodic);
        servers.Add(sink.Install(ues));
        UdpClientHelper client;
        client.SetAttribute("MaxPackets", UintegerValue(0xFFFFFFFF));
        client.SetAttribute("PacketSize", UintegerValue(64));
        client.SetAttribute("Interval", TimeValue(MilliSeconds(10)));
        client.SetAttribute("RemotePort", UintegerValue(portPeriodic));
        EpsBearer bearer(EpsBearer::NGBR_LOW_LAT_EMBB);
        Ptr<EpcTft> tft = Create<EpcTft>();
        EpcTft::PacketFilter filter;
        filter.localPortStart = portPeriodic;
        filter.localPortEnd = portPeriodic;
        tft->Add(filter);
        for (uint32_t i = 0; i < trafficUes && i < ues.GetN(); ++i)
        {
            client.SetAttribute("RemoteAddress", AddressValue(ueIfaces.GetAddress(i)));
            clients.Add(client.Install(remoteHost));
            nrHelper->ActivateDedicatedEpsBearer(ueDevs.Get(i), bearer, tft);
        }
    }
    if (trafficUes > 0 && wantFull)
    {
        UdpServerHelper sink(portFull);
        servers.Add(sink.Install(ues));
        UdpClientHelper client;
        client.SetAttribute("MaxPackets", UintegerValue(0xFFFFFFFF));
        client.SetAttribute("PacketSize", UintegerValue(1000));
        client.SetAttribute("Interval", TimeValue(MicroSeconds(200)));
        client.SetAttribute("RemotePort", UintegerValue(portFull));
        EpsBearer bearer(EpsBearer::NGBR_VIDEO_TCP_DEFAULT);
        Ptr<EpcTft> tft = Create<EpcTft>();
        EpcTft::PacketFilter filter;
        filter.localPortStart = portFull;
        filter.localPortEnd = portFull;
        tft->Add(filter);
        for (uint32_t i = 0; i < trafficUes && i < ues.GetN(); ++i)
        {
            client.SetAttribute("RemoteAddress", AddressValue(ueIfaces.GetAddress(i)));
            clients.Add(client.Install(remoteHost));
            nrHelper->ActivateDedicatedEpsBearer(ueDevs.Get(i), bearer, tft);
        }
    }

    Time start = MilliSeconds(100);
    servers.Start(start);
    clients.Start(start);
    servers.Stop(Seconds(simTime));
    clients.Stop(Seconds(simTime));

    Simulator::Stop(Seconds(simTime));
    if (!timingLog.empty() && timingPeriodMs > 0.0)
    {
        Simulator::Schedule(MilliSeconds(timingPeriodMs),
                            &WriteTimingSample,
                            timingLog,
                            timingPeriodMs);
    }
    Simulator::Run();
    Simulator::Destroy();
    std::cout << "CORNET_BENCH done sim_s=" << simTime << " realtime=" << realtime << "\n";
    return 0;
}
