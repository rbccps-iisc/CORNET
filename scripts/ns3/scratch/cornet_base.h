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
};

// Reads newline-delimited {"name","x","y","z"} from a Unix socket on a side thread.
// Poll() is called from the simulator thread. The server may be the CORNET PositionServer.
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
                CornetPosition sample;
                if (Parse(buf.substr(0, nl), sample))
                {
                    std::lock_guard<std::mutex> lock(m_mu);
                    m_pending.push_back(sample);
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

#endif
