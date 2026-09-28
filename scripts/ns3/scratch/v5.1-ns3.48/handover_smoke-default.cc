/*
 * v5.1 handover smoke: two gNBs, one UE moving between them.
 * Asserts at least one HandoverTotalTime trace record. Not a co-simulation.
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/nr-module.h"
#include "ns3/isotropic-antenna-model.h"

#include <iostream>

using namespace ns3;

namespace
{
uint32_t g_handoverRecords = 0;

void
OnHandoverTotalTime(uint64_t imsi, uint16_t sourceCellId, uint16_t targetCellId, Time totalTime)
{
    ++g_handoverRecords;
    std::cout << "HandoverTotalTime imsi=" << imsi << " source=" << sourceCellId
              << " target=" << targetCellId << " seconds=" << totalTime.GetSeconds() << std::endl;
}
} // namespace

int
main(int argc, char* argv[])
{
    double simTime = 12.0;
    CommandLine cmd;
    cmd.AddValue("simTime", "Simulation time in seconds", simTime);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(1);
    Config::SetDefault("ns3::NrGnbRrc::HandoverTriggeringDelay", TimeValue(MilliSeconds(40)));

    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();
    nrHelper->SetAttribute("UseIdealRrc", BooleanValue(false));
    nrHelper->SetSchedulerTypeId(TypeId::LookupByName("ns3::NrMacSchedulerTdmaPF"));
    nrHelper->SetHandoverAlgorithmType("ns3::NrA3RsrpHandoverAlgorithm");
    nrHelper->SetHandoverAlgorithmAttribute("Hysteresis", DoubleValue(1.5));
    nrHelper->SetHandoverAlgorithmAttribute("TimeToTrigger", TimeValue(MilliSeconds(128)));

    Ptr<NrPointToPointEpcHelper> epcHelper = CreateObject<NrPointToPointEpcHelper>();
    nrHelper->SetEpcHelper(epcHelper);

    NodeContainer gnbNodes;
    gnbNodes.Create(2);
    NodeContainer ueNodes;
    ueNodes.Create(1);

    Ptr<ListPositionAllocator> gnbPositions = CreateObject<ListPositionAllocator>();
    gnbPositions->Add(Vector(1000.0, 0.0, 0.0));
    gnbPositions->Add(Vector(2000.0, 0.0, 0.0));
    MobilityHelper gnbMobility;
    gnbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    gnbMobility.SetPositionAllocator(gnbPositions);
    gnbMobility.Install(gnbNodes);

    MobilityHelper ueMobility;
    ueMobility.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    ueMobility.Install(ueNodes);
    ueNodes.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 0.0));
    ueNodes.Get(0)->GetObject<ConstantVelocityMobilityModel>()->SetVelocity(Vector(150.0, 0.0, 0.0));

    nrHelper->SetUeAntennaTypeId(IsotropicAntennaModel::GetTypeId().GetName());
    nrHelper->SetGnbAntennaTypeId(IsotropicAntennaModel::GetTypeId().GetName());

    Ptr<NrChannelHelper> channelHelper = CreateObject<NrChannelHelper>();
    channelHelper->ConfigurePropagationFactory(FriisPropagationLossModel::GetTypeId());
    CcBwpCreator ccBwpCreator;
    CcBwpCreator::SimpleOperationBandConf bandConf(2.8e9, 10e6, static_cast<uint8_t>(1));
    OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);
    channelHelper->AssignChannelsToBands({band});
    BandwidthPartInfoPtrVector allBwps = CcBwpCreator::GetAllBwps({band});

    NetDeviceContainer gnbDevices = nrHelper->InstallGnbDevice(gnbNodes, allBwps);
    NetDeviceContainer ueDevices = nrHelper->InstallUeDevice(ueNodes, allBwps);

    NodeContainer remoteHostContainer;
    remoteHostContainer.Create(1);
    InternetStackHelper internet;
    internet.Install(remoteHostContainer);
    PointToPointHelper p2ph;
    p2ph.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gb/s")));
    p2ph.SetDeviceAttribute("Mtu", UintegerValue(1500));
    p2ph.SetChannelAttribute("Delay", TimeValue(Seconds(0.010)));
    NetDeviceContainer internetDevices = p2ph.Install(epcHelper->GetPgwNode(), remoteHostContainer.Get(0));
    Ipv4AddressHelper ipv4h;
    ipv4h.SetBase("1.0.0.0", "255.0.0.0");
    ipv4h.Assign(internetDevices);
    Ipv4StaticRoutingHelper ipv4RoutingHelper;
    ipv4RoutingHelper.GetStaticRouting(remoteHostContainer.Get(0)->GetObject<Ipv4>())
        ->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);
    internet.Install(ueNodes);
    epcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevices));
    nrHelper->AttachToGnb(ueDevices.Get(0), gnbDevices.Get(0));
    nrHelper->AddX2Interface(gnbNodes);

    Config::ConnectWithoutContext("/NodeList/*/DeviceList/*/NrGnbRrc/HandoverTotalTime",
                                  MakeCallback(&OnHandoverTotalTime));

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    Simulator::Destroy();

    if (g_handoverRecords == 0)
    {
        std::cerr << "handover smoke failed: no HandoverTotalTime record\n";
        return 1;
    }
    std::cout << "handover smoke records=" << g_handoverRecords << std::endl;
    return 0;
}
