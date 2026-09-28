/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * CORNET scratch-script helpers.
 *
 * ParseCornetArgs reads the virtual-port contract the NS-3 plugin passes:
 *   --tun{i}=name,ip   one TapBridge per middleware ip_list entry
 *   --sensorPort=N     default 5001
 *   --controlPort=N    default 5002
 *
 * The header is installed next to scratch sources. New scripts may call
 * ParseCornetArgs instead of reimplementing the scan. Zero --tun args means
 * middleware is off and no TapBridge should be created.
 */

#ifndef CORNET_BASE_H
#define CORNET_BASE_H

#include <atomic>
#include <cstdint>
#include <exception>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

struct CornetArgs
{
    uint16_t sensorPort{5001};
    uint16_t controlPort{5002};
    std::vector<std::pair<std::string, std::string>> tuns;
};

inline CornetArgs
ParseCornetArgs(int argc, char* argv[])
{
    CornetArgs args;
    for (int i = 1; i < argc; ++i)
    {
        std::string token(argv[i] ? argv[i] : "");
        if (token.rfind("--", 0) == 0)
        {
            token = token.substr(2);
        }
        const auto eq = token.find('=');
        if (eq == std::string::npos)
        {
            continue;
        }
        const std::string key = token.substr(0, eq);
        const std::string value = token.substr(eq + 1);
        if (key == "sensorPort")
        {
            args.sensorPort = static_cast<uint16_t>(std::stoi(value));
        }
        else if (key == "controlPort")
        {
            args.controlPort = static_cast<uint16_t>(std::stoi(value));
        }
        else if (key.rfind("tun", 0) == 0 && key.size() > 3)
        {
            const auto comma = value.find(',');
            if (comma != std::string::npos)
            {
                args.tuns.emplace_back(value.substr(0, comma), value.substr(comma + 1));
            }
        }
    }
    return args;
}

struct CornetPosition
{
    std::string name;
    double x{0.0};
    double y{0.0};
    double z{0.0};
    double vx{0.0};
    double vy{0.0};
    double vz{0.0};
    bool hasVelocity{false};
};

struct CornetSite
{
    std::string name;
    double x{0.0};
    double y{0.0};
    double z{0.0};
};

struct CornetDevice
{
    std::string name;
    std::string kind;
    std::string traffic;
    double x{0.0};
    double y{0.0};
    double z{0.0};
    int channel{-1};
    bool mobile{false};
};

struct CornetLayout
{
    std::string channel{"UMa"};
    std::string deployment;
    double isdM{0.0};
    int sectors{1};
    bool wraparound{false};
    bool blockage{false};
    bool indoor{false};
    double channelUpdateMs{0.0};
    int backgroundUesPerCell{0};
    uint32_t seed{1};
    int numNonSelfBlocking{-1};
    int wifiChannel{36};
    std::vector<CornetSite> sites;
    std::vector<CornetSite> robots;
    std::vector<CornetDevice> devices;
};

// Reads newline-delimited positions from a Unix socket on a side thread.
// Accepted lines are {"name","x","y","z"} and
// {"nodes":{"<name>":[x,y,z,vx,vy,vz]}}. Poll() runs on the simulator thread.
// The server may be the CORNET PositionServer. Mobility models are updated
// from Poll(), not from this thread.
class CornetPositionFeed
{
  public:
    void Start(const std::string& path)
    {
        if (path.empty())
        {
            return;
        }
        m_stop = false;
        m_thread = std::thread([this, path]() { ReadLoop(path); });
    }

    std::vector<CornetPosition> Poll()
    {
        std::lock_guard<std::mutex> lock(m_mu);
        std::vector<CornetPosition> out;
        out.swap(m_pending);
        return out;
    }

    void Stop()
    {
        m_stop = true;
        if (m_thread.joinable())
        {
            m_thread.join();
        }
    }

  private:
    static bool Parse(const std::string& line, CornetPosition& out)
    {
        const auto nameKey = line.find("\"name\"");
        if (nameKey == std::string::npos)
        {
            return false;
        }
        const auto q1 = line.find('"', line.find(':', nameKey) + 1);
        const auto q2 = q1 == std::string::npos ? std::string::npos : line.find('"', q1 + 1);
        if (q1 == std::string::npos || q2 == std::string::npos)
        {
            return false;
        }
        out.name = line.substr(q1 + 1, q2 - q1 - 1);
        auto number = [&line](const char* key, double& dest) {
            const auto pos = line.find(key);
            if (pos == std::string::npos)
            {
                return false;
            }
            const auto colon = line.find(':', pos);
            if (colon == std::string::npos)
            {
                return false;
            }
            try
            {
                dest = std::stod(line.substr(colon + 1));
            }
            catch (const std::exception&)
            {
                return false;
            }
            return true;
        };
        return number("\"x\"", out.x) && number("\"y\"", out.y) && number("\"z\"", out.z);
    }

    static std::vector<CornetPosition> ParseNodes(const std::string& line)
    {
        std::vector<CornetPosition> out;
        const auto nodes = line.find("\"nodes\"");
        if (nodes == std::string::npos)
        {
            return out;
        }
        std::size_t cursor = nodes;
        while (true)
        {
            const auto key = line.find('"', cursor);
            if (key == std::string::npos)
            {
                break;
            }
            const auto keyEnd = line.find('"', key + 1);
            if (keyEnd == std::string::npos)
            {
                break;
            }
            const std::string name = line.substr(key + 1, keyEnd - key - 1);
            cursor = keyEnd + 1;
            if (name == "nodes")
            {
                continue;
            }
            const auto bracket = line.find('[', cursor);
            if (bracket == std::string::npos)
            {
                break;
            }
            double values[6] = {0, 0, 0, 0, 0, 0};
            std::size_t at = bracket + 1;
            int count = 0;
            while (count < 6 && at < line.size())
            {
                while (at < line.size() && (line[at] == ' ' || line[at] == ','))
                {
                    ++at;
                }
                if (at >= line.size() || line[at] == ']')
                {
                    break;
                }
                try
                {
                    std::size_t used = 0;
                    values[count] = std::stod(line.substr(at), &used);
                    at += used;
                    ++count;
                }
                catch (const std::exception&)
                {
                    break;
                }
            }
            if (count >= 3)
            {
                CornetPosition sample;
                sample.name = name;
                sample.x = values[0];
                sample.y = values[1];
                sample.z = values[2];
                if (count >= 6)
                {
                    sample.vx = values[3];
                    sample.vy = values[4];
                    sample.vz = values[5];
                    sample.hasVelocity = true;
                }
                out.push_back(sample);
            }
            cursor = at;
        }
        return out;
    }

    void ReadLoop(std::string path)
    {
        int fd = -1;
        for (int attempt = 0; attempt < 50 && !m_stop && fd < 0; ++attempt)
        {
            fd = socket(AF_UNIX, SOCK_STREAM, 0);
            if (fd < 0)
            {
                return;
            }
            sockaddr_un addr{};
            addr.sun_family = AF_UNIX;
            if (path.size() >= sizeof(addr.sun_path))
            {
                close(fd);
                return;
            }
            std::char_traits<char>::copy(addr.sun_path, path.c_str(), path.size() + 1);
            if (connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0)
            {
                close(fd);
                fd = -1;
                usleep(100000);
            }
        }
        if (fd < 0)
        {
            return;
        }
        std::string buf;
        char tmp[512];
        while (!m_stop)
        {
            const ssize_t n = recv(fd, tmp, sizeof(tmp), 0);
            if (n <= 0)
            {
                break;
            }
            buf.append(tmp, static_cast<size_t>(n));
            std::size_t nl;
            while ((nl = buf.find('\n')) != std::string::npos)
            {
                const std::string text = buf.substr(0, nl);
                CornetPosition sample;
                if (Parse(text, sample))
                {
                    std::lock_guard<std::mutex> lock(m_mu);
                    m_pending.push_back(sample);
                }
                else
                {
                    const auto many = ParseNodes(text);
                    if (!many.empty())
                    {
                        std::lock_guard<std::mutex> lock(m_mu);
                        m_pending.insert(m_pending.end(), many.begin(), many.end());
                    }
                }
                buf.erase(0, nl + 1);
            }
        }
        close(fd);
    }

    std::atomic<bool> m_stop{false};
    std::mutex m_mu;
    std::vector<CornetPosition> m_pending;
    std::thread m_thread;
};

inline std::string
CornetJsonString(const std::string& text, const std::string& key)
{
    const auto pos = text.find("\"" + key + "\"");
    if (pos == std::string::npos)
    {
        return "";
    }
    const auto colon = text.find(':', pos);
    const auto q1 = text.find('"', colon + 1);
    if (colon == std::string::npos || q1 == std::string::npos)
    {
        return "";
    }
    const auto q2 = text.find('"', q1 + 1);
    if (q2 == std::string::npos)
    {
        return "";
    }
    return text.substr(q1 + 1, q2 - q1 - 1);
}

inline bool
CornetJsonBool(const std::string& text, const std::string& key, bool fallback)
{
    const auto pos = text.find("\"" + key + "\"");
    if (pos == std::string::npos)
    {
        return fallback;
    }
    const auto colon = text.find(':', pos);
    if (colon == std::string::npos)
    {
        return fallback;
    }
    const auto tail = text.substr(colon + 1, 8);
    if (tail.find("true") != std::string::npos)
    {
        return true;
    }
    if (tail.find("false") != std::string::npos)
    {
        return false;
    }
    return fallback;
}

inline double
CornetJsonNumber(const std::string& text, const std::string& key, double fallback)
{
    const auto pos = text.find("\"" + key + "\"");
    if (pos == std::string::npos)
    {
        return fallback;
    }
    const auto colon = text.find(':', pos);
    if (colon == std::string::npos)
    {
        return fallback;
    }
    try
    {
        return std::stod(text.substr(colon + 1));
    }
    catch (const std::exception&)
    {
        return fallback;
    }
}

inline std::vector<CornetSite>
CornetJsonSites(const std::string& text, const std::string& key)
{
    std::vector<CornetSite> sites;
    const auto pos = text.find("\"" + key + "\"");
    if (pos == std::string::npos)
    {
        return sites;
    }
    const auto begin = text.find('[', pos);
    const auto end = text.find(']', begin);
    if (begin == std::string::npos || end == std::string::npos)
    {
        return sites;
    }
    const std::string body = text.substr(begin, end - begin);
    std::size_t cursor = 0;
    while ((cursor = body.find('{', cursor)) != std::string::npos)
    {
        const auto close = body.find('}', cursor);
        if (close == std::string::npos)
        {
            break;
        }
        const std::string item = body.substr(cursor, close - cursor);
        CornetSite site;
        site.name = CornetJsonString(item, "name");
        site.x = CornetJsonNumber(item, "x", 0.0);
        site.y = CornetJsonNumber(item, "y", 0.0);
        site.z = CornetJsonNumber(item, "z", 0.0);
        sites.push_back(site);
        cursor = close + 1;
    }
    return sites;
}

inline std::vector<CornetDevice>
CornetJsonDevices(const std::string& text)
{
    std::vector<CornetDevice> devices;
    const auto pos = text.find("\"devices\"");
    if (pos == std::string::npos)
    {
        return devices;
    }
    const auto begin = text.find('[', pos);
    const auto end = text.find(']', begin);
    if (begin == std::string::npos || end == std::string::npos)
    {
        return devices;
    }
    const std::string body = text.substr(begin, end - begin);
    std::size_t cursor = 0;
    while ((cursor = body.find('{', cursor)) != std::string::npos)
    {
        const auto close = body.find('}', cursor);
        if (close == std::string::npos)
        {
            break;
        }
        const std::string item = body.substr(cursor, close - cursor);
        CornetDevice device;
        device.name = CornetJsonString(item, "name");
        device.kind = CornetJsonString(item, "kind");
        device.traffic = CornetJsonString(item, "traffic");
        device.x = CornetJsonNumber(item, "x", 0.0);
        device.y = CornetJsonNumber(item, "y", 0.0);
        device.z = CornetJsonNumber(item, "z", 0.0);
        device.channel = static_cast<int>(CornetJsonNumber(item, "channel", -1));
        device.mobile = CornetJsonBool(item, "mobile", false);
        devices.push_back(device);
        cursor = close + 1;
    }
    return devices;
}

inline CornetLayout
LoadCornetLayout(const std::string& path)
{
    CornetLayout layout;
    std::ifstream in(path.c_str());
    if (!in)
    {
        return layout;
    }
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    const std::string channel = CornetJsonString(text, "channel");
    if (!channel.empty())
    {
        layout.channel = channel;
    }
    layout.deployment = CornetJsonString(text, "deployment");
    layout.isdM = CornetJsonNumber(text, "isd_m", 0.0);
    layout.sectors = static_cast<int>(CornetJsonNumber(text, "sectors", 1));
    layout.wraparound = CornetJsonBool(text, "wraparound", false);
    layout.blockage = CornetJsonBool(text, "blockage", false);
    layout.indoor = CornetJsonBool(text, "indoor", false);
    layout.channelUpdateMs = CornetJsonNumber(text, "channel_update_ms", 0.0);
    layout.backgroundUesPerCell = static_cast<int>(CornetJsonNumber(text, "background_ues_per_cell", 0));
    layout.seed = static_cast<uint32_t>(CornetJsonNumber(text, "seed", 1));
    const auto blockers = text.find("\"num_non_self_blocking\"");
    if (blockers != std::string::npos)
    {
        const auto colon = text.find(':', blockers);
        const auto tail = colon == std::string::npos ? std::string() : text.substr(colon + 1, 10);
        if (tail.find("null") == std::string::npos)
        {
            layout.numNonSelfBlocking =
                static_cast<int>(CornetJsonNumber(text, "num_non_self_blocking", 4));
        }
    }
    layout.wifiChannel = static_cast<int>(CornetJsonNumber(text, "wifi_channel", 36));
    layout.sites = CornetJsonSites(text, "sites");
    layout.robots = CornetJsonSites(text, "robots");
    layout.devices = CornetJsonDevices(text);
    return layout;
}

#endif
