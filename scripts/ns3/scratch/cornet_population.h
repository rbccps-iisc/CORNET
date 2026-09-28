/* CORNET population devices for the catalogue scratch programs.
 * NR and LTE map traffic.profile onto 5G-LENA NGMN/3GPP generators.
 * full_buffer and periodic_iot are UDP. xr uses the 3GPP generic video model.
 */

#ifndef CORNET_POPULATION_H
#define CORNET_POPULATION_H

#include "cornet_base.h"

#include "ns3/applications-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/names.h"
#include "ns3/network-module.h"
#include "ns3/traffic-generator-3gpp-generic-video.h"
#include "ns3/traffic-generator-helper.h"
#include "ns3/traffic-generator-ngmn-ftp-multi.h"
#include "ns3/traffic-generator-ngmn-gaming.h"
#include "ns3/traffic-generator-ngmn-video.h"
#include "ns3/traffic-generator-ngmn-voip.h"

#include <string>
#include <vector>

namespace

{

inline void
AddCornetPopulation(const CornetLayout& layout, ns3::NodeContainer& ues, std::vector<std::string>& traffic)
{
    ns3::NodeContainer extra;
    for (const auto& device : layout.devices)
    {
        if (device.kind == "wifi_neighbour")
        {
            continue;
        }
        extra.Create(1);
        ns3::Ptr<ns3::Node> node = extra.Get(extra.GetN() - 1);
        ns3::MobilityHelper mobility;
        mobility.SetMobilityModel(device.mobile ? "ns3::ConstantVelocityMobilityModel"
                                                : "ns3::ConstantPositionMobilityModel");
        mobility.Install(node);
        node->GetObject<ns3::MobilityModel>()->SetPosition(ns3::Vector(device.x, device.y, device.z));
        if (!device.name.empty())
        {
            ns3::Names::Add(device.name, node);
        }
        traffic.push_back(device.traffic);
    }
    ues.Add(extra);
}

inline void
InstallCornetProfile(ns3::Ptr<ns3::Node> remote, ns3::Ipv4Address dest, const std::string& profile)
{
    const uint16_t port = 1235;
    if (profile.empty() || profile == "full_buffer" || profile == "periodic_iot")
    {
        ns3::UdpClientHelper client;
        client.SetAttribute("MaxPackets", ns3::UintegerValue(0xffffffff));
        client.SetAttribute("Interval", ns3::TimeValue(profile == "periodic_iot" ? ns3::Seconds(1.0) : ns3::MilliSeconds(profile == "full_buffer" ? 1.0 : 10.0)));
        client.SetAttribute("PacketSize", ns3::UintegerValue(profile == "full_buffer" ? 1400 : 64));
        client.SetAttribute("RemoteAddress", ns3::AddressValue(dest));
        client.SetAttribute("RemotePort", ns3::UintegerValue(port));
        ns3::ApplicationContainer apps = client.Install(remote);
        apps.Start(ns3::Seconds(0.1));
        return;
    }
    ns3::TypeId typeId;
    if (profile == "ftp")
    {
        typeId = ns3::TrafficGeneratorNgmnFtpMulti::GetTypeId();
    }
    else if (profile == "video")
    {
        typeId = ns3::TrafficGeneratorNgmnVideo::GetTypeId();
    }
    else if (profile == "voip")
    {
        typeId = ns3::TrafficGeneratorNgmnVoip::GetTypeId();
    }
    else if (profile == "gaming")
    {
        typeId = ns3::TrafficGeneratorNgmnGaming::GetTypeId();
    }
    else if (profile == "xr")
    {
        typeId = ns3::TrafficGenerator3gppGenericVideo::GetTypeId();
    }
    else
    {
        NS_FATAL_ERROR("unknown traffic profile " << profile);
    }
    ns3::TrafficGeneratorHelper helper("ns3::UdpSocketFactory", ns3::Address(), typeId);
    helper.SetAttribute("Remote", ns3::AddressValue(ns3::InetSocketAddress(dest, port)));
    ns3::ApplicationContainer apps = helper.Install(remote);
    apps.Start(ns3::Seconds(0.1));
}

} // namespace

#endif
