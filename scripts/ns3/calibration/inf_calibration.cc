/*
 * InF large-scale calibration (TR 38.901 Table 7.8-7).
 *
 * Creates each Indoor Factory scenario through NR's channel helper, drops the
 * 18-site lattice and indoor UEs from that table, and records serving-cell
 * coupling loss. Isotropic 0 dBi antennas make coupling loss equal to path loss.
 *
 * The layout follows Ramos et al., WNS3 2022. This file is not their example.
 *
 *   ./ns3 run "inf_calibration --outputDir=<dir>"
 */

#include "ns3/core-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/nr-module.h"
#include "ns3/propagation-module.h"
#include "ns3/spectrum-module.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <vector>

using namespace ns3;

namespace
{

struct Hall
{
    const char* name;
    double length;
    double width;
    double spacing;
    double bsHeight;
};

const Hall kHalls[] = {
    {"InF-SL", 120.0, 60.0, 20.0, 1.5},
    {"InF-DL", 300.0, 150.0, 50.0, 1.5},
    {"InF-SH", 300.0, 150.0, 50.0, 8.0},
    {"InF-DH", 120.0, 60.0, 20.0, 8.0},
};

Ptr<MobilityModel>
Place(const Vector& pos)
{
    Ptr<Node> node = CreateObject<Node>();
    Ptr<MobilityModel> mob = CreateObject<ConstantPositionMobilityModel>();
    node->AggregateObject(mob);
    mob->SetPosition(pos);
    return mob;
}

std::vector<Vector>
Lattice(const Hall& hall)
{
    std::vector<Vector> sites;
    const double margin = hall.spacing / 2.0;
    for (double y = margin; y < hall.width - 1e-6; y += hall.spacing)
    {
        for (double x = margin; x < hall.length - 1e-6; x += hall.spacing)
        {
            sites.emplace_back(x, y, hall.bsHeight);
        }
    }
    return sites;
}

Ptr<PropagationLossModel>
InfLoss(const char* scenario, bool shadowing)
{
    Ptr<NrChannelHelper> helper = CreateObject<NrChannelHelper>();
    helper->ConfigureFactories(scenario, "Default", "ThreeGpp");
    helper->SetPathlossAttribute("Frequency", DoubleValue(3.5e9));
    helper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(shadowing));
    Ptr<SpectrumChannel> channel = helper->CreateChannel(NrChannelHelper::INIT_PROPAGATION);
    Ptr<PropagationLossModel> loss = channel->GetPropagationLossModel();
    NS_ABORT_MSG_IF(loss == nullptr, "NR channel helper did not install an InF loss model");
    return loss;
}

double
Percentile(std::vector<double> values, double fraction)
{
    NS_ABORT_MSG_IF(values.empty(), "empty sample");
    std::sort(values.begin(), values.end());
    const double index = fraction * static_cast<double>(values.size() - 1);
    const std::size_t lo = static_cast<std::size_t>(std::floor(index));
    const std::size_t hi = static_cast<std::size_t>(std::ceil(index));
    if (lo == hi)
    {
        return values[lo];
    }
    const double weight = index - static_cast<double>(lo);
    return values[lo] * (1.0 - weight) + values[hi] * weight;
}

void
WriteSvg(const std::string& path, const std::vector<double>& sorted, const std::string& title)
{
    const double width = 640.0;
    const double height = 360.0;
    const double margin = 48.0;
    const double xmin = sorted.front();
    const double xmax = sorted.back();
    const double span = std::max(1e-6, xmax - xmin);
    std::ostringstream poly;
    for (std::size_t i = 0; i < sorted.size(); ++i)
    {
        const double x = margin + (sorted[i] - xmin) / span * (width - 2.0 * margin);
        const double y =
            height - margin - (static_cast<double>(i) / static_cast<double>(sorted.size() - 1)) *
                                  (height - 2.0 * margin);
        poly << x << "," << y << " ";
    }
    std::ofstream out(path);
    out << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\"" << height
        << "\">\n";
    out << "<rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n";
    out << "<text x=\"" << margin << "\" y=\"28\">" << title << "</text>\n";
    out << "<polyline fill=\"none\" stroke=\"#1f4e79\" stroke-width=\"2\" points=\"" << poly.str()
        << "\"/>\n";
    out << "<text x=\"" << margin << "\" y=\"" << height - 12 << "\">" << xmin
        << " dB</text>\n";
    out << "<text x=\"" << width - 140 << "\" y=\"" << height - 12 << "\">" << xmax
        << " dB</text>\n";
    out << "</svg>\n";
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string outputDir = ".";
    uint32_t nUe = 180;
    CommandLine cmd;
    cmd.AddValue("outputDir", "Directory for CSV, SVG, and the verdict", outputDir);
    cmd.AddValue("nUe", "Indoor UEs per sub-scenario", nUe);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(1);

    Ptr<PropagationLossModel> anchorLoss = InfLoss("InF-SL", false);
    Ptr<ThreeGppPropagationLossModel> infAnchor = DynamicCast<ThreeGppPropagationLossModel>(anchorLoss);
    NS_ABORT_MSG_IF(infAnchor == nullptr, "InF-SL did not create a 3GPP propagation loss model");
    infAnchor->SetChannelConditionModel(CreateObject<AlwaysLosChannelConditionModel>());
    Ptr<MobilityModel> bs = Place(Vector(0.0, 0.0, 1.5));
    Ptr<MobilityModel> ue = Place(Vector(10.0, 0.0, 1.5));
    const double anchorDb = -anchorLoss->CalcRxPower(0.0, bs, ue);
    const double anchorRef = 63.6773;
    const bool anchorOk = std::abs(anchorDb - anchorRef) <= 0.1;

    std::ofstream samples(outputDir + "/coupling_loss.csv");
    std::ofstream summary(outputDir + "/summary.csv");
    samples << "scenario,ue,coupling_loss_db\n";
    summary << "scenario,n,median_db,p05_db,p95_db\n";

    std::ostringstream verdict;
    verdict << "# InF calibration verdict\n\n";
    verdict << "Layout: TR 38.901 Table 7.8-7, 3.5 GHz, isotropic antennas, serving cell by "
               "minimum path loss. Shadowing is on for the CDFs.\n\n";
    verdict << "Formula anchor, InF-SL LOS, shadowing off, d3D = 10 m: " << anchorDb
            << " dB (Table 7.4.1-1 reference " << anchorRef << " dB). "
            << (anchorOk ? "Within 0.1 dB.\n\n" : "Outside 0.1 dB.\n\n");
    verdict << "TR 38.901 section 7.8.4 points the serving-cell coupling-loss curves at "
               "R1-1909704. Those numeric medians are not in this tree, so no sub-scenario "
               "is within a checked 1 dB of that reference.\n\n";
    verdict << "Verdict: uncalibrated. Failing sub-scenarios: InF-SL, InF-DL, InF-SH, InF-DH.\n\n";
    verdict << "| Scenario | Sites | UEs | Median (dB) | 5% | 95% |\n|---|---:|---:|---:|---:|---:|\n";

    for (const Hall& hall : kHalls)
    {
        const std::vector<Vector> sites = Lattice(hall);
        NS_ABORT_MSG_IF(sites.size() != 18, "Table 7.8-7 requires 18 base stations");
        std::vector<Ptr<MobilityModel>> bsMobility;
        bsMobility.reserve(sites.size());
        for (const Vector& pos : sites)
        {
            bsMobility.push_back(Place(pos));
        }

        Ptr<PropagationLossModel> loss = InfLoss(hall.name, true);
        Ptr<UniformRandomVariable> x = CreateObject<UniformRandomVariable>();
        Ptr<UniformRandomVariable> y = CreateObject<UniformRandomVariable>();
        x->SetAttribute("Min", DoubleValue(0.0));
        x->SetAttribute("Max", DoubleValue(hall.length));
        y->SetAttribute("Min", DoubleValue(0.0));
        y->SetAttribute("Max", DoubleValue(hall.width));

        std::vector<double> coupling;
        coupling.reserve(nUe);
        for (uint32_t i = 0; i < nUe; ++i)
        {
            Vector pos(0.0, 0.0, 1.5);
            for (uint32_t attempt = 0; attempt < 1000; ++attempt)
            {
                pos = Vector(x->GetValue(), y->GetValue(), 1.5);
                bool clear = true;
                for (const Vector& site : sites)
                {
                    const double dx = pos.x - site.x;
                    const double dy = pos.y - site.y;
                    if (std::hypot(dx, dy) < 1.0)
                    {
                        clear = false;
                        break;
                    }
                }
                if (clear)
                {
                    break;
                }
            }
            Ptr<MobilityModel> ueMob = Place(pos);
            double best = 1e9;
            for (const Ptr<MobilityModel>& site : bsMobility)
            {
                best = std::min(best, -loss->CalcRxPower(0.0, site, ueMob));
            }
            coupling.push_back(best);
            samples << hall.name << "," << i << "," << best << "\n";
        }

        std::vector<double> sorted = coupling;
        std::sort(sorted.begin(), sorted.end());
        const double median = Percentile(coupling, 0.5);
        const double p05 = Percentile(coupling, 0.05);
        const double p95 = Percentile(coupling, 0.95);
        summary << hall.name << "," << coupling.size() << "," << median << "," << p05 << "," << p95
                << "\n";
        verdict << "| " << hall.name << " | " << sites.size() << " | " << coupling.size() << " | "
                << median << " | " << p05 << " | " << p95 << " |\n";
        WriteSvg(outputDir + "/cdf-" + hall.name + ".svg",
                 sorted,
                 std::string(hall.name) + " serving-cell coupling loss CDF");
        std::cout << hall.name << " sites=" << sites.size() << " median_db=" << median << "\n";
    }

    std::ofstream verdictFile(outputDir + "/VERDICT.md");
    verdictFile << verdict.str();
    std::cout << "formula_anchor_db=" << anchorDb << " ok=" << (anchorOk ? "yes" : "no") << "\n";
    std::cout << "verdict=uncalibrated\n";
    return anchorOk ? 0 : 1;
}
