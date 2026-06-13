/*
 * scratch_template-default.cc — CORNET NS-3 scratch script template
 *
 * PURPOSE
 * -------
 * This file implements ONLY the CORNET virtual-port contract (design D14–D18).
 * Copy it as the starting point for any new CORNET NS-3 experiment script.
 * Add experiment-specific radio setup and traffic configuration below the
 * "ADD YOUR EXPERIMENT SETUP HERE" comment.
 *
 * CORNET VIRTUAL-PORT CONTRACT
 * ----------------------------
 * The CORNET plugin (ns3_plugin.py) creates Linux TUN interfaces and passes
 * their names/IPs to NS-3 via --tun{i}=name,ip CLI args:
 *
 *   --tun0=cornet0,10.0.0.1  --tun1=cornet1,10.0.0.2  ...
 *
 * This script reads those args and creates one TapBridgeHelper per arg.
 * TAP bridge count == --tun{i} arg count, NOT numUes.
 * Background UEs (no TAP bridge) are not counted.
 *
 * Port numbers are forwarded from config.yaml MiddlewareConfig:
 *   --sensorPort=5001   (default)
 *   --controlPort=5002  (default)
 *
 * NAMING CONVENTION
 * -----------------
 * Filename: <task-script-base>-<profile-suffix>.cc
 *   "-default" means: accepts --networkPreset CLI arg at runtime.
 * The simulation_script field in config.yaml must match this filename exactly
 * (minus the .cc extension): e.g. simulation_script: scratch_template-default
 *
 * To compile manually:
 *   cp scratch_template-default.cc $NS3_DIR/scratch/
 *   cd $NS3_DIR && ./ns3 build
 *   ./ns3 run scratch_template-default -- --tun0=cornet0,10.0.0.1
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/tap-bridge-module.h"
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CornetScriptTemplate");

int main(int argc, char *argv[])
{
    // ── Experiment parameters (customize these) ───────────────────────────────
    uint32_t numUes = 2;       // Total UE count — may be > number of CORNET TAP bridges
    double   simTime = 60.0;   // Simulation duration in seconds

    // ── CORNET infrastructure port parameters (design D16) ───────────────────
    // These are forwarded from config.yaml MiddlewareConfig fields.
    // Defaults match MiddlewareConfig.sensor_port / control_port defaults.
    uint16_t sensorPort  = 5001;
    uint16_t controlPort = 5002;

    // ── CORNET virtual-port contract args (design D14/D15) ───────────────────
    // The CORNET plugin passes --tun{i}=name,ip for each entry in ip_list.
    // We collect up to CORNET_MAX_TUNS; unused slots stay empty and are skipped.
    const uint32_t CORNET_MAX_TUNS = 8;
    std::vector<std::string> cornetTunArgs(CORNET_MAX_TUNS, "");

    CommandLine cmd;
    cmd.AddValue("numUes",       "Total number of UEs in simulation",   numUes);
    cmd.AddValue("simTime",      "Simulation duration in seconds",      simTime);
    cmd.AddValue("sensorPort",   "UDP port for robot sensor data flow",  sensorPort);
    cmd.AddValue("controlPort",  "UDP port for robot control commands",  controlPort);

    // Register --tun{i} args — MUST be done before cmd.Parse()
    for (uint32_t k = 0; k < CORNET_MAX_TUNS; k++)
    {
        cmd.AddValue("tun" + std::to_string(k),
                     "CORNET TUN interface from plugin: name,ip",
                     cornetTunArgs[k]);
    }

    cmd.Parse(argc, argv);

    GlobalValue::Bind("SimulatorImplementationType", StringValue("ns3::RealtimeSimulatorImpl"));
    GlobalValue::Bind("ChecksumEnabled", BooleanValue(true));

    LogComponentEnable("CornetScriptTemplate", LOG_LEVEL_INFO);

    NS_LOG_INFO("=== CORNET Script Template ===");
    NS_LOG_INFO("numUes: " << numUes << "  simTime: " << simTime << "s");
    NS_LOG_INFO("sensorPort: " << sensorPort << "  controlPort: " << controlPort);

    // ── ADD YOUR EXPERIMENT SETUP HERE ───────────────────────────────────────
    //
    // 1. Create NodeContainers (ueNodes, gnbNodes, etc.)
    // 2. Install InternetStackHelper
    // 3. Set up mobility models
    // 4. Configure and install LTE/NR or WiFi devices
    // 5. Assign IP addresses
    // 6. Set up routing
    // 7. (Optional) Install traffic applications
    //
    // Example skeleton:
    //
    //   NodeContainer ueNodes, gnbNodes;
    //   ueNodes.Create(numUes);
    //   gnbNodes.Create(1);
    //   // ... configure LTE/NR, install devices, assign IPs ...
    //   NetDeviceContainer ueDevices = ...;
    //
    // ─────────────────────────────────────────────────────────────────────────

    // ── CORNET TAP bridge setup (design D14/D15) ──────────────────────────────
    // MUST come AFTER nodes and devices are created and IPs assigned.
    // Create one TAP bridge per --tun{i} arg, NOT per numUes.
    // The CORNET plugin will only pass args for UEs it manages (those in ip_list).
    //
    // Replace the placeholder ueNodes / ueDevices references below with your
    // actual NodeContainer / NetDeviceContainer once your experiment is set up.
    //
    // NodeContainer ueNodes = ...;        // YOUR UE nodes
    // NetDeviceContainer ueDevices = ...; // YOUR UE net devices
    //
    // Uncomment and adapt when your experiment setup is ready:
    /*
    TapBridgeHelper tapBridge;
    tapBridge.SetAttribute("Mode", StringValue("UseLocal"));
    uint32_t tapCount = 0;
    for (uint32_t i = 0; i < CORNET_MAX_TUNS && tapCount < ueNodes.GetN(); i++)
    {
        if (cornetTunArgs[i].empty()) break;
        const std::string& arg = cornetTunArgs[i];
        std::string tapName = arg.substr(0, arg.find(','));
        NS_ABORT_MSG_IF(tapName.empty(), "--tun" << i << " has empty interface name");
        tapBridge.SetAttribute("DeviceName", StringValue(tapName));
        tapBridge.Install(ueNodes.Get(tapCount), ueDevices.Get(tapCount));
        NS_LOG_INFO("TAP bridge: " << tapName << " -> UE " << tapCount);
        tapCount++;
    }
    if (tapCount == 0)
        NS_LOG_INFO("No --tun{i} args; TAP bridges skipped (middleware.enabled=false)");
    */

    NS_LOG_INFO("Starting simulation...");
    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    Simulator::Destroy();
    NS_LOG_INFO("Simulation completed");
    return 0;
}
