/*
 * Origin: CORNET3.0@202eb78 network/ns-3/scratch/remote_robot_control.cc
 * Patch-set: v2.4-ns3.38 (NS-3 3.38 + NR v2.4)
 * Copied: 2026-06-02
 *
 * To check for upstream drift:
 *   diff scripts/ns3/scratch/v2.4-ns3.38/remote_robot_control-default.cc \
 *        <CORNET3_DIR>/network/ns-3/scratch/remote_robot_control.cc
 *
 * Naming: <task-script-base>-<profile-suffix>.cc
 *   "-default" means: accepts --networkPreset CLI arg at runtime
 *   Profile-specific variants (e.g. -urllc, -embb) would be separate files.
 *
 * Remote Robot Control Scenario
 * Low-latency control of remote robot over 5G network
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/ipv4-static-routing-helper.h"
#include "ns3/lte-module.h"
#include "ns3/point-to-point-epc-helper.h"
#include "ns3/nr-module.h"
#include "ns3/nr-helper.h"
#include "ns3/nr-mac-scheduler-ofdma-edf.h"
#include "ns3/nr-mac-scheduler-ofdma-aoi.h"
#include "ns3/nr-point-to-point-epc-helper.h"
#include "ns3/ideal-beamforming-helper.h"
#include "ns3/cc-bwp-helper.h"
#include "ns3/isotropic-antenna-model.h"
#include "ns3/rng-seed-manager.h"
#include "ns3/tap-bridge-module.h"
#include "ns3/epc-helper.h"
#include <fstream>
#include <cmath>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("RemoteRobotControlScenario");

namespace
{

uint16_t
GetLteBandwidthRbs(double bandwidthHz)
{
    struct LteBandwidthOption
    {
        double bandwidthHz;
        uint16_t rbs;
    };

    static const LteBandwidthOption options[] = {
        {1.4e6, 6},
        {3.0e6, 15},
        {5.0e6, 25},
        {10.0e6, 50},
        {15.0e6, 75},
        {20.0e6, 100},
    };

    uint16_t selected = 100;
    double bestDiff = std::abs(bandwidthHz - options[0].bandwidthHz);

    for (const auto& option : options)
    {
        const double diff = std::abs(bandwidthHz - option.bandwidthHz);
        if (diff < bestDiff)
        {
            bestDiff = diff;
            selected = option.rbs;
        }
    }

    return selected;
}

} // namespace

int main(int argc, char *argv[])
{
    // Scenario parameters
    uint32_t numUes = 2;  // Robot + Controller
    uint32_t numGnbs = 1;
    double simTime = 60.0;
    double frequency = 3.5e9;  // 3.5 GHz
    double bandwidth = 100e6;  // 100 MHz
    uint16_t numerology = 1;   // 30 kHz SCS
    double txPower = 23.0;
    double gnbTxPower = 43.0;
    std::string networkPreset = "5g_nr";
    double delayMs = 8.0;
    double jitterMs = 0.0;
    double lossRate = 0.0;
    uint32_t rngRun = 1;
    uint16_t controlPort = 5002;
    uint16_t sensorPort = 5001;
    bool enablePcap = false;
    bool enableFlowMonitor = false;

    // URLLC / Configured-Grant parameters
    bool configuredGrant = false;  // Emulate CG via fixed-MCS + low-delay scheduling
    bool fixedMcsUl = false;
    bool fixedMcsDl = false;
    uint16_t startingMcsUl = 12;
    uint16_t startingMcsDl = 4;
    uint32_t n0Delay = 0;           // DL DCI decode + data decode delay (slots)
    uint32_t n1Delay = 2;           // HARQ-ACK preparation delay (slots)
    uint32_t n2Delay = 2;           // UL DCI decode + data prep delay (slots)
    double tbDecodeLatencyUs = 100; // Transport block decode latency (us)
    uint16_t symbolsPerSlot = 14;
    std::string tddPattern = ""; // Empty = use NR default
    std::string schedulerType = "";
    bool prbRandomAllocation = false;
    uint32_t pdcpRepetitions = 0;
    uint32_t pdcpRepDelayMs = 1;

    // Background traffic parameters
    uint32_t numBackgroundUes = 0;   // Number of background UEs generating competing traffic
    double bgDataRateMbps = 10.0;    // Per-UE background data rate in Mbps

    // Command line arguments
    CommandLine cmd;
    cmd.AddValue("simTime", "Simulation time in seconds", simTime);
    cmd.AddValue("numUes", "Number of UEs", numUes);
    cmd.AddValue("frequency", "Central frequency in Hz", frequency);
    cmd.AddValue("bandwidth", "Bandwidth in Hz", bandwidth);
    cmd.AddValue("numerology", "NR numerology (0-4)", numerology);
    cmd.AddValue("txPower", "UE transmit power in dBm", txPower);
    cmd.AddValue("gnbTxPower", "Base-station transmit power in dBm", gnbTxPower);
    cmd.AddValue("networkPreset", "Network preset label (lte, 5g_nr, 5g_nr_urllc)", networkPreset);
    cmd.AddValue("delayMs", "One-way link delay in ms", delayMs);
    cmd.AddValue("jitterMs", "Jitter placeholder in ms (for metadata only)", jitterMs);
    cmd.AddValue("lossRate", "Packet loss probability [0,1]", lossRate);
    cmd.AddValue("rngRun", "NS-3 RNG run number for repeated experiments", rngRun);
    cmd.AddValue("configuredGrant", "Enable CG-like scheduling (fixed-MCS, min processing delays)", configuredGrant);
    cmd.AddValue("fixedMcsUl", "Use fixed MCS for UL", fixedMcsUl);
    cmd.AddValue("fixedMcsDl", "Use fixed MCS for DL", fixedMcsDl);
    cmd.AddValue("startingMcsUl", "Starting MCS for UL (used when fixedMcsUl=true)", startingMcsUl);
    cmd.AddValue("startingMcsDl", "Starting MCS for DL (used when fixedMcsDl=true)", startingMcsDl);
    cmd.AddValue("n0Delay", "N0 processing delay in slots", n0Delay);
    cmd.AddValue("n1Delay", "N1 HARQ-ACK delay in slots", n1Delay);
    cmd.AddValue("n2Delay", "N2 UL data preparation delay in slots", n2Delay);
    cmd.AddValue("tbDecodeLatencyUs", "TB decode latency in microseconds", tbDecodeLatencyUs);
    cmd.AddValue("symbolsPerSlot", "Symbols per slot (14 or 7 for mini-slots)", symbolsPerSlot);
    cmd.AddValue("tddPattern", "TDD pattern string e.g. F|F|F|F|F|F|F|F|F|F|", tddPattern);
    cmd.AddValue("schedulerType", "NR scheduler type (rr or edf)", schedulerType);
    cmd.AddValue("prbRandomAllocation", "Randomize PRB assignment order per slot (frequency diversity)", prbRandomAllocation);
    cmd.AddValue("pdcpRepetitions", "Number of extra PDCP PDU copies (0 = off)", pdcpRepetitions);
    cmd.AddValue("pdcpRepDelayMs", "Delay between successive PDCP copies (ms)", pdcpRepDelayMs);
    cmd.AddValue("numBackgroundUes", "Number of background UEs generating competing traffic", numBackgroundUes);
    cmd.AddValue("bgDataRateMbps", "Per-UE background data rate in Mbps", bgDataRateMbps);
    cmd.AddValue("enableTraces", "Enable NR radio traces (writes large .txt files to CWD)", enablePcap);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(rngRun);

    if (networkPreset == "lte")
    {
        if (delayMs <= 0.0) delayMs = 20.0;
        if (lossRate <= 0.0) lossRate = 0.01;
    }
    else if (networkPreset == "5g_nr_urllc")
    {
        if (delayMs <= 0.0) delayMs = 2.0;
        if (lossRate <= 0.0) lossRate = 0.0001;
    }
    else
    {
        if (delayMs <= 0.0) delayMs = 8.0;
        if (lossRate <= 0.0) lossRate = 0.002;
    }

    if (lossRate < 0.0)
    {
        lossRate = 0.0;
    }
    if (lossRate > 1.0)
    {
        lossRate = 1.0;
    }

    GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    GlobalValue::Bind("ChecksumEnabled", BooleanValue(true));

    // Enable logging
    LogComponentEnable("RemoteRobotControlScenario", LOG_LEVEL_INFO);

    NS_LOG_INFO("=== Remote Robot Control Scenario ===");
    NS_LOG_INFO("Number of UEs: " << numUes << " (Robot + Controller)");
    NS_LOG_INFO("Number of background UEs: " << numBackgroundUes);
    NS_LOG_INFO("Number of gNBs: " << numGnbs);
    NS_LOG_INFO("Simulation time: " << simTime << "s");
    NS_LOG_INFO("Network preset: " << networkPreset);
    NS_LOG_INFO("Frequency: " << frequency / 1e9 << " GHz");
    NS_LOG_INFO("Bandwidth: " << bandwidth / 1e6 << " MHz");
    NS_LOG_INFO("Numerology: " << numerology);
    NS_LOG_INFO("UE Tx Power: " << txPower << " dBm");
    NS_LOG_INFO("gNB/eNB Tx Power: " << gnbTxPower << " dBm");
    NS_LOG_INFO("Profile delay target (metadata): " << delayMs << " ms");
    NS_LOG_INFO("Profile jitter target (metadata): " << jitterMs << " ms");
    NS_LOG_INFO("Profile loss target (metadata): " << (lossRate * 100.0) << "%");
    NS_LOG_INFO("RNG run: " << rngRun);
    NS_LOG_INFO("Configured-Grant emulation: " << (configuredGrant ? "ON" : "OFF"));
    if (configuredGrant)
    {
        NS_LOG_INFO("  Fixed MCS UL: " << fixedMcsUl << " (MCS=" << startingMcsUl << ")");
        NS_LOG_INFO("  Fixed MCS DL: " << fixedMcsDl << " (MCS=" << startingMcsDl << ")");
        NS_LOG_INFO("  N0/N1/N2 delay: " << n0Delay << "/" << n1Delay << "/" << n2Delay);
        NS_LOG_INFO("  TB decode latency: " << tbDecodeLatencyUs << " us");
        NS_LOG_INFO("  Symbols per slot: " << symbolsPerSlot);
    }
    if (!schedulerType.empty())
    {
        NS_LOG_INFO("Scheduler override: " << schedulerType);
    }
    if (prbRandomAllocation)
    {
        NS_LOG_INFO("PRB randomization: ON");
    }
    if (pdcpRepetitions > 0)
    {
        NS_LOG_INFO("PDCP repetitions: " << pdcpRepetitions << " extra copies @ " << pdcpRepDelayMs << " ms");
    }
    if (numBackgroundUes > 0)
    {
        NS_LOG_INFO("Background UEs: " << numBackgroundUes << " @ " << bgDataRateMbps << " Mbps each");
        NS_LOG_INFO("Total offered load: " << (numBackgroundUes * bgDataRateMbps) << " Mbps");
    }

    // Create nodes
    NodeContainer ueNodes;
    ueNodes.Create(numUes);
    
    NodeContainer gnbNodes;
    gnbNodes.Create(numGnbs);

    NS_LOG_INFO("UE 0: Robot (sensor sender)");
    NS_LOG_INFO("UE 1: Controller (control sender)");

    // Set up mobility for gNB (stationary)
    MobilityHelper gnbMobility;
    Ptr<ListPositionAllocator> gnbPositions = CreateObject<ListPositionAllocator>();
    gnbPositions->Add(Vector(50.0, 50.0, 30.0));  // Central gNB
    gnbMobility.SetPositionAllocator(gnbPositions);
    gnbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    gnbMobility.Install(gnbNodes);

    // Set up mobility for UEs (stationary)
    MobilityHelper ueMobility;
    Ptr<ListPositionAllocator> uePositions = CreateObject<ListPositionAllocator>();
    uePositions->Add(Vector(10.0, 50.0, 1.5));   // Robot position
    uePositions->Add(Vector(90.0, 50.0, 1.5));   // Controller position
    ueMobility.SetPositionAllocator(uePositions);
    ueMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    ueMobility.Install(ueNodes);

    InternetStackHelper internet;
    NetDeviceContainer gnbDevices;
    NetDeviceContainer ueDevices;
    Ipv4InterfaceContainer ueInterfaces;
    BandwidthPartInfoPtrVector allBwps;  // Stored for background UE installation
    NodeContainer bgUeNodes;
    NetDeviceContainer bgUeDevices;
    Ipv4InterfaceContainer bgUeInterfaces;

    // Helpers must outlive Simulator::Run() -- EPC helper owns PGW/SGW/MME state.
    Ptr<EpcHelper> epcHelper;
    Ptr<LteHelper> lteHelper;
    Ptr<NrHelper> nrHelper;

    if (networkPreset == "lte")
    {
        NS_LOG_INFO("Configuring LTE radio + EPC packet path");

        Config::SetDefault("ns3::LteEnbRrc::SrsPeriodicity", UintegerValue(320));
        Config::SetDefault("ns3::LteHelper::UseIdealRrc", BooleanValue(false));
        Config::SetDefault("ns3::LteEnbPhy::TxPower", DoubleValue(gnbTxPower));
        Config::SetDefault("ns3::LteUePhy::TxPower", DoubleValue(txPower));

        Ptr<PointToPointEpcHelper> lteEpcHelper = CreateObject<PointToPointEpcHelper>();
        epcHelper = lteEpcHelper;
        lteHelper = CreateObject<LteHelper>();
        lteHelper->SetEpcHelper(lteEpcHelper);
        lteHelper->SetSchedulerType("ns3::RrFfMacScheduler");
        lteHelper->SetHandoverAlgorithmType("ns3::NoOpHandoverAlgorithm");

        const uint16_t lteBandwidthRbs = GetLteBandwidthRbs(bandwidth);
        lteHelper->SetEnbDeviceAttribute("DlBandwidth", UintegerValue(lteBandwidthRbs));
        lteHelper->SetEnbDeviceAttribute("UlBandwidth", UintegerValue(lteBandwidthRbs));

        gnbDevices = lteHelper->InstallEnbDevice(gnbNodes);

        internet.Install(ueNodes);
        ueDevices = lteHelper->InstallUeDevice(ueNodes);
        ueInterfaces = lteEpcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevices));
        lteHelper->AttachToClosestEnb(ueDevices, gnbDevices);

        Ipv4StaticRoutingHelper ipv4RoutingHelper;
        for (uint32_t i = 0; i < ueNodes.GetN(); ++i)
        {
            Ptr<Ipv4StaticRouting> ueStaticRouting =
                ipv4RoutingHelper.GetStaticRouting(ueNodes.Get(i)->GetObject<Ipv4>());
            ueStaticRouting->SetDefaultRoute(lteEpcHelper->GetUeDefaultGatewayAddress(), 1);
        }

        if (enablePcap)
        {
            lteHelper->EnablePhyTraces();
            lteHelper->EnableMacTraces();
            lteHelper->EnableRlcTraces();
            lteHelper->EnablePdcpTraces();
            NS_LOG_INFO("LTE radio traces enabled");
        }
    }
    else
    {
        NS_LOG_INFO("Configuring 5G NR radio + EPC packet path");

        Ptr<NrPointToPointEpcHelper> nrEpcHelper = CreateObject<NrPointToPointEpcHelper>();
        epcHelper = nrEpcHelper;
        nrHelper = CreateObject<NrHelper>();
        nrHelper->SetEpcHelper(nrEpcHelper);

        Ptr<IdealBeamformingHelper> bfHelper = CreateObject<IdealBeamformingHelper>();
        bfHelper->SetAttribute("BeamformingMethod",
                               TypeIdValue(DirectPathBeamforming::GetTypeId()));
        nrHelper->SetBeamformingHelper(bfHelper);
        nrHelper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(false));
        nrHelper->SetGnbPhyAttribute("Numerology", UintegerValue(numerology));
        nrHelper->SetGnbPhyAttribute("TxPower", DoubleValue(gnbTxPower));
        nrHelper->SetUePhyAttribute("TxPower", DoubleValue(txPower));

        if (schedulerType == "edf")
        {
            nrHelper->SetSchedulerTypeId(NrMacSchedulerOfdmaEdf::GetTypeId());
        }
        else if (schedulerType == "aoi")
        {
            nrHelper->SetSchedulerTypeId(NrMacSchedulerOfdmaAoi::GetTypeId());
        }
        else if (schedulerType == "rr")
        {
            nrHelper->SetSchedulerTypeId(NrMacSchedulerOfdmaRR::GetTypeId());
        }

        // ---- URLLC / Configured-Grant emulation ----
        // Based on: A. Larrañaga et al., "An open-source implementation and
        // validation of 5G NR Configured-Grant for URLLC in ns-3 5G-LENA",
        // ref: https://gitlab.com/ns-3-dev-nr-configuredgrant/ns-3-dev/-/tree/ns-3.36-cg
        //
        // The upstream CG branch adds "CG" and "ConfigurationTime" attributes
        // to NrUeMac/NrGnbMac/NrUePhy/NrGnbPhy (ns-3.36).  Our NR v2.4
        // (ns-3.38) does not include that fork.  We emulate CG-like behaviour
        // with the knobs that *are* available:
        //   1. Fixed UL/DL MCS  → deterministic TB size (no SR/BSR overhead)
        //   2. Minimum processing delays N0=0, N1=0, N2=0
        //   3. Reduced TB decode latency
        //   4. OFDMA-RR scheduler (frequency-domain, like CG allocations)
        //   5. Disabled HARQ retransmissions (single-shot, bounded latency)
        //   6. Optional mini-slot via SymbolsPerSlot = 7
        //   7. UL-heavy TDD pattern for uplink-centric URLLC traffic
        if (configuredGrant)
        {
            NS_LOG_INFO("Applying Configured-Grant URLLC scheduling knobs");

            // (1) Fixed MCS — eliminates adaptive MCS "search" delay
            if (fixedMcsUl)
            {
                nrHelper->SetSchedulerAttribute("FixedMcsUl", BooleanValue(true));
                nrHelper->SetSchedulerAttribute("StartingMcsUl", UintegerValue(startingMcsUl));
            }
            if (fixedMcsDl)
            {
                nrHelper->SetSchedulerAttribute("FixedMcsDl", BooleanValue(true));
                nrHelper->SetSchedulerAttribute("StartingMcsDl", UintegerValue(startingMcsDl));
            }

            // (2) Processing delays — minimise pipeline latency
            nrHelper->SetGnbPhyAttribute("N0Delay", UintegerValue(n0Delay));
            nrHelper->SetGnbPhyAttribute("N1Delay", UintegerValue(n1Delay));
            nrHelper->SetGnbPhyAttribute("N2Delay", UintegerValue(n2Delay));

            // (3) TB decode latency
            nrHelper->SetGnbPhyAttribute("TbDecodeLatency",
                                          TimeValue(MicroSeconds(tbDecodeLatencyUs)));

            // (4) Scheduler choice. Default remains OFDMA-RR unless overridden.
            if (schedulerType.empty())
            {
                nrHelper->SetSchedulerTypeId(NrMacSchedulerOfdmaRR::GetTypeId());
            }

            // (5) Disable HARQ retransmissions for bounded one-shot latency
            nrHelper->SetSchedulerAttribute("EnableHarqReTx", BooleanValue(false));
            Config::SetDefault("ns3::NrHelper::HarqEnabled", BooleanValue(false));

            // (6) Mini-slots via SymbolsPerSlot (7 = half-slot ~ 2-symbol mini-slot pairs)
            if (symbolsPerSlot != 14)
            {
                nrHelper->SetGnbPhyAttribute("SymbolsPerSlot",
                                              UintegerValue(symbolsPerSlot));
            }

            // (7) Custom TDD pattern (UL-heavy for uplink sensor traffic)
            if (!tddPattern.empty())
            {
                nrHelper->SetGnbPhyAttribute("Pattern", StringValue(tddPattern));
            }
        }

        // (8) PRB randomization for frequency diversity (independent of CG)
        if (prbRandomAllocation)
        {
            nrHelper->SetSchedulerAttribute("RandomizePrb", BooleanValue(true));
        }

        // PDCP repetition (applies to all NR flows; Config::SetDefault before device install)
        if (pdcpRepetitions > 0)
        {
            Config::SetDefault("ns3::LtePdcp::PdcpRepetitions", UintegerValue(pdcpRepetitions));
            Config::SetDefault("ns3::LtePdcp::PdcpRepetitionDelayMs", UintegerValue(pdcpRepDelayMs));
        }

        CcBwpCreator ccBwpCreator;
        const uint8_t numCcPerBand = 1;
        CcBwpCreator::SimpleOperationBandConf bandConf(frequency,
                                                       bandwidth,
                                                       numCcPerBand,
                                                       BandwidthPartInfo::UMa);
        OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);
        nrHelper->InitializeOperationBand(&band);
        allBwps = CcBwpCreator::GetAllBwps({band});

        nrHelper->SetUeAntennaAttribute("NumRows", UintegerValue(1));
        nrHelper->SetUeAntennaAttribute("NumColumns", UintegerValue(1));
        nrHelper->SetUeAntennaAttribute(
            "AntennaElement",
            PointerValue(CreateObject<IsotropicAntennaModel>()));
        nrHelper->SetGnbAntennaAttribute("NumRows", UintegerValue(4));
        nrHelper->SetGnbAntennaAttribute("NumColumns", UintegerValue(8));
        nrHelper->SetGnbAntennaAttribute(
            "AntennaElement",
            PointerValue(CreateObject<IsotropicAntennaModel>()));

        gnbDevices = nrHelper->InstallGnbDevice(gnbNodes, allBwps);
        ueDevices = nrHelper->InstallUeDevice(ueNodes, allBwps);

        for (auto it = gnbDevices.Begin(); it != gnbDevices.End(); ++it)
        {
            DynamicCast<NrGnbNetDevice>(*it)->UpdateConfig();
        }
        for (auto it = ueDevices.Begin(); it != ueDevices.End(); ++it)
        {
            DynamicCast<NrUeNetDevice>(*it)->UpdateConfig();
        }

        internet.Install(ueNodes);
        ueInterfaces = nrEpcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevices));
        nrHelper->AttachToClosestEnb(ueDevices, gnbDevices);

        Ipv4StaticRoutingHelper ipv4RoutingHelper;
        for (uint32_t i = 0; i < ueNodes.GetN(); ++i)
        {
            Ptr<Ipv4StaticRouting> ueStaticRouting =
                ipv4RoutingHelper.GetStaticRouting(ueNodes.Get(i)->GetObject<Ipv4>());
            ueStaticRouting->SetDefaultRoute(nrEpcHelper->GetUeDefaultGatewayAddress(), 1);
        }

        if (enablePcap)
        {
            nrHelper->EnableTraces();
            NS_LOG_INFO("NR radio traces enabled");
        }

        // ---- Background UEs for cell loading (inside NR block so band/allBwps stay valid) ----
        if (numBackgroundUes > 0)
        {
            bgUeNodes.Create(numBackgroundUes);

            // Place background UEs in a ring around gNB (radius 30-70m)
            MobilityHelper bgMobility;
            Ptr<ListPositionAllocator> bgPositions = CreateObject<ListPositionAllocator>();
            for (uint32_t i = 0; i < numBackgroundUes; ++i)
            {
                double angle = 2.0 * M_PI * i / numBackgroundUes;
                double radius = 30.0 + (i % 5) * 10.0;
                bgPositions->Add(Vector(50.0 + radius * std::cos(angle),
                                        50.0 + radius * std::sin(angle),
                                        1.5));
            }
            bgMobility.SetPositionAllocator(bgPositions);
            bgMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
            bgMobility.Install(bgUeNodes);

            internet.Install(bgUeNodes);

            bgUeDevices = nrHelper->InstallUeDevice(bgUeNodes, allBwps);
            for (auto it = bgUeDevices.Begin(); it != bgUeDevices.End(); ++it)
            {
                DynamicCast<NrUeNetDevice>(*it)->UpdateConfig();
            }
            bgUeInterfaces = nrEpcHelper->AssignUeIpv4Address(NetDeviceContainer(bgUeDevices));
            nrHelper->AttachToClosestEnb(bgUeDevices, gnbDevices);

            Ipv4StaticRoutingHelper bgRoutingHelper;
            for (uint32_t i = 0; i < bgUeNodes.GetN(); ++i)
            {
                Ptr<Ipv4StaticRouting> r =
                    bgRoutingHelper.GetStaticRouting(bgUeNodes.Get(i)->GetObject<Ipv4>());
                r->SetDefaultRoute(nrEpcHelper->GetUeDefaultGatewayAddress(), 1);
            }

            // Install OnOff UDP sources (UL) on each background UE -> PGW sink
            uint16_t bgPort = 9000;
            Ptr<Node> pgw = nrEpcHelper->GetPgwNode();
            Ipv4Address pgwAddr = pgw->GetObject<Ipv4>()->GetAddress(1, 0).GetLocal();

            PacketSinkHelper sinkHelper("ns3::UdpSocketFactory",
                                         InetSocketAddress(Ipv4Address::GetAny(), bgPort));
            sinkHelper.Install(pgw);

            std::string bgRate = std::to_string(static_cast<uint64_t>(bgDataRateMbps * 1e6)) + "bps";
            for (uint32_t i = 0; i < numBackgroundUes; ++i)
            {
                OnOffHelper onOff("ns3::UdpSocketFactory",
                                  InetSocketAddress(pgwAddr, bgPort));
                onOff.SetConstantRate(DataRate(bgRate), 1400);
                ApplicationContainer app = onOff.Install(bgUeNodes.Get(i));
                app.Start(Seconds(0.5));
                app.Stop(Seconds(simTime - 0.5));
            }

            NS_LOG_INFO("✓ " << numBackgroundUes << " background UEs installed, "
                        << bgDataRateMbps << " Mbps each (UL to PGW)");
        }
    }

    NS_LOG_INFO("Robot (UE 0) IP: " << ueInterfaces.GetAddress(0));
    NS_LOG_INFO("Controller (UE 1) IP: " << ueInterfaces.GetAddress(1));

    // Setup TAP bridge interfaces for robot and controller (first 2 UEs only)
    TapBridgeHelper tapBridge;
    tapBridge.SetAttribute("Mode", StringValue("UseLocal"));
    
    for (uint32_t i = 0; i < numUes; i++)
    {
        std::string tapName = (i == 0) ? "tap-robot" : "tap-controller";
        tapBridge.SetAttribute("DeviceName", StringValue(tapName));
        tapBridge.Install(ueNodes.Get(i), ueDevices.Get(i));
        
        NS_LOG_INFO("✓ TAP bridge: " << tapName << " -> UE " << i);
    }

    // NOTE: Do NOT call Ipv4GlobalRoutingHelper::PopulateRoutingTables() here.
    // LTE/NR net devices are not standard links -- GlobalRouter cannot discover
    // their LSAs and will abort.  Static routes (set above) are sufficient.

    NS_LOG_INFO("Nodes, mobility, TAP bridges, and LTE/NR radio path configured");

    NS_LOG_INFO("Waiting for external UDP traffic via TAP bridges");
    NS_LOG_INFO("Expected flows: robot->controller on port " << sensorPort
                 << ", controller->robot on port " << controlPort);

    // Flow Monitor -- install only on UE nodes (not all EPC internal nodes)
    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor;
    if (enableFlowMonitor)
    {
        monitor = flowmon.Install(ueNodes);
        NS_LOG_INFO("Flow monitor installed on UE nodes");
    }

    // Latency tracking
    std::string latencyFile = "control_latency.csv";
    std::ofstream latFile;
    latFile.open(latencyFile);
    latFile << "Time,Flow,InstantDelay_ms" << std::endl;

    // Track instantaneous latency every 10ms
    for (double t = 0.5; t < simTime; t += 0.01)
    {
        Simulator::Schedule(Seconds(t), [&latFile, &monitor, &flowmon, t, controlPort, sensorPort]() {
            if (monitor)
            {
                Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
                FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();
                
                for (auto const &stat : stats)
                {
                    if (stat.second.rxPackets > 0)
                    {
                        double avgDelay = stat.second.delaySum.GetSeconds() / stat.second.rxPackets;
                        Ipv4FlowClassifier::FiveTuple tuple = classifier->FindFlow(stat.first);
                        std::string flowType = "Other";
                        if (tuple.destinationPort == controlPort)
                        {
                            flowType = "Control";
                        }
                        else if (tuple.destinationPort == sensorPort)
                        {
                            flowType = "Sensor";
                        }
                        latFile << t << "," << flowType << "," << (avgDelay * 1000) << std::endl;
                    }
                }
            }
        });
    }

    NS_LOG_INFO("Starting simulation...");

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    latFile.close();

    // Print flow monitor statistics
    if (enableFlowMonitor)
    {
        NS_LOG_INFO("\n=== Flow Monitor Statistics ===");
        monitor->CheckForLostPackets();
        Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
        FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();

        double totalThroughput = 0.0;
        
        for (auto const &stat : stats)
        {
            Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(stat.first);
            double throughput = stat.second.rxBytes * 8.0 / simTime / 1000.0;  // kbps
            totalThroughput += throughput;
            
            double avgDelay = 0.0;
            double jitter = 0.0;
            double lossRate = 0.0;
            
            if (stat.second.rxPackets > 0)
            {
                avgDelay = stat.second.delaySum.GetSeconds() / stat.second.rxPackets;
                jitter = stat.second.jitterSum.GetSeconds() / stat.second.rxPackets;
            }
            
            if (stat.second.txPackets > 0)
            {
                lossRate = (stat.second.txPackets - stat.second.rxPackets) * 100.0 / stat.second.txPackets;
            }
            
            std::string flowType = "OTHER";
            if (t.destinationPort == controlPort)
            {
                flowType = "CONTROL";
            }
            else if (t.destinationPort == sensorPort)
            {
                flowType = "SENSOR";
            }
            
            NS_LOG_INFO("\n=== " << flowType << " FLOW ===");
            NS_LOG_INFO("  " << t.sourceAddress << " -> " << t.destinationAddress);
            NS_LOG_INFO("  Throughput: " << throughput << " kbps");
            NS_LOG_INFO("  Packets: " << stat.second.rxPackets << "/" << stat.second.txPackets);
            NS_LOG_INFO("  Loss Rate: " << lossRate << "%");
            NS_LOG_INFO("  Average Delay: " << (avgDelay * 1000) << " ms");
            NS_LOG_INFO("  Average Jitter: " << (jitter * 1000) << " ms");
            
            // URLLC requirements check
            bool meetsLatency = (avgDelay * 1000) < 10.0;  // < 10ms
            bool meetsReliability = lossRate < 0.001;       // 99.999% reliability
            
            NS_LOG_INFO("  Latency requirement (< 10ms): " << (meetsLatency ? "PASS" : "FAIL"));
            NS_LOG_INFO("  Reliability requirement (< 0.001% loss): " << (meetsReliability ? "PASS" : "FAIL"));
        }
        
        NS_LOG_INFO("\n=== Summary ===");
        NS_LOG_INFO("Total Throughput: " << totalThroughput << " kbps");
        NS_LOG_INFO("Latency trace saved to: " << latencyFile);
    }

    Simulator::Destroy();
    NS_LOG_INFO("Simulation completed");

    return 0;
}
