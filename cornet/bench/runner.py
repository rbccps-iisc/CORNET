"""Execute NS-3, Gazebo and combined benchmark suites."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from cornet.bench.grids import expand_suite, format_dry_run
from cornet.bench.report import append_row, classify_rows, read_rows, write_summary
from cornet.bench.systeminfo import find_ns3_dir, has_cap_net_admin, machine_info, software_info
from cornet.bench.worlds import generate_world, model_path_for, resolve_world
from cornet.telemetry import parse_gz_stats_factors, parse_ns3_timing_log, percentile

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "ns3"
    / "scratch"
    / "v2.4-ns3.38"
    / "bench_nr_multicell-default.cc"
)


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    return {
        "mean": sum(values) / len(values),
        "p5": percentile(values, 5),
        "min": min(values),
        "p99": percentile(values, 99),
    }


def _base_row(run: dict[str, Any], machine: dict, software: dict) -> dict[str, Any]:
    row: dict[str, Any] = {
        "suite": run.get("suite", ""),
        "config_id": run.get("id", run.get("name", "")),
        "repeat": run.get("repeat", 0),
        "seed": run.get("seed", 1),
        "pin_cpu": run.get("pin_cpu", False),
        "tap": run.get("tap", False),
        "tap_status": "",
        "ns3_lane": software.get("ns3_lane", ""),
        "gazebo_version": software.get("gazebo_version", ""),
        "ros_version": software.get("ros_version", ""),
    }
    row.update(machine)
    ns3 = run.get("ns3") or run
    gazebo = run.get("gazebo") or run
    for key in (
        "sites",
        "sectors",
        "ues_per_cell",
        "traffic",
        "channel_update_ms",
        "numerology",
        "wraparound",
        "scheduler",
    ):
        if key in ns3:
            row[key] = ns3[key]
    for key in ("world", "robots", "actors", "camera", "step_ms"):
        if key in gazebo and run.get("suite") != "ns3":
            row[key] = gazebo[key]
        elif key in run and run.get("suite") == "gazebo":
            row[key] = run[key]
    return row


def _install_bench_script(ns3_dir: Path) -> str:
    dest_dir = ns3_dir / "scratch"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _SCRIPT.name
    if not dest.is_file() or dest.read_bytes() != _SCRIPT.read_bytes():
        shutil.copy2(_SCRIPT, dest)
    stem = _SCRIPT.stem
    if stem.endswith("-default"):
        stem = stem[: -len("-default")]
    return stem


def _ns3_command(
    ns3_dir: Path,
    cfg: dict[str, Any],
    *,
    sim_time: float,
    realtime: bool,
    seed: int,
    timing_log: Path | None,
    no_build: bool,
    output_dir: Path,
    prefix: list[str] | None = None,
) -> list[str]:
    target = _install_bench_script(ns3_dir)
    output_dir = Path(output_dir).resolve()
    if timing_log is not None:
        timing_log = Path(timing_log).resolve()
    plot_dir = str(output_dir)
    if not plot_dir.endswith("/"):
        plot_dir += "/"
    cmd = list(prefix or [])
    cmd += [str(ns3_dir / "ns3"), "run"]
    if no_build:
        cmd.append("--no-build")
    cmd += [
        target,
        "--",
        f"--sites={cfg['sites']}",
        f"--sectors={cfg['sectors']}",
        f"--uesPerCell={cfg['ues_per_cell']}",
        f"--traffic={cfg['traffic']}",
        f"--channelUpdateMs={cfg['channel_update_ms']}",
        f"--numerology={cfg['numerology']}",
        f"--wraparound={'true' if cfg.get('wraparound') else 'false'}",
        f"--realtime={'true' if realtime else 'false'}",
        f"--scheduler={cfg.get('scheduler', 'rr')}",
        f"--simTime={sim_time}",
        f"--rngRun={seed}",
        f"--outputDir={plot_dir}",
    ]
    if timing_log is not None:
        cmd.append(f"--timingLog={timing_log}")
        cmd.append("--timingPeriodMs=10")
    return cmd


def _kill_group(proc: subprocess.Popen) -> None:
    """Kill a timed-out NS-3 wrapper and the simulator it spawned."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def _run_process(cmd: list[str], *, cwd: Path | None, timeout: float, env: dict | None = None) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_group(proc)
        try:
            output, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            output = exc.stdout
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return 124, time.perf_counter() - t0, (output or "") + "\nTIMEOUT"
    return proc.returncode if proc.returncode is not None else 0, time.perf_counter() - t0, output or ""


def ensure_ns3_built(ns3_dir: Path, work: Path) -> str | None:
    """Compile the benchmark script once. Returns an error string on failure."""
    cmd = _ns3_command(
        ns3_dir,
        {
            "sites": 1,
            "sectors": 1,
            "ues_per_cell": 0,
            "traffic": "periodic",
            "channel_update_ms": 0,
            "numerology": 1,
            "wraparound": False,
            "scheduler": "rr",
        },
        sim_time=0.05,
        realtime=False,
        seed=1,
        timing_log=None,
        no_build=False,
        output_dir=work,
    )
    code, _wall, output = _run_process(cmd, cwd=ns3_dir, timeout=1800)
    (work / "build.log").write_text(output)
    if code != 0:
        tail = "\n".join(output.splitlines()[-20:])
        return f"NS-3 benchmark script failed to build (exit {code}): {tail}"
    return None


def run_ns3_suite(runs: list[dict[str, Any]], results: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    ns3_dir = find_ns3_dir()
    machine = machine_info()
    software = software_info(ns3_dir)
    csv_path = results / "results.csv"
    if ns3_dir is None:
        print("skipping ns3 suite: NS-3 not found (set NS3_DIR)")
        return
    work = results / "ns3-build"
    work.mkdir(parents=True, exist_ok=True)
    error = ensure_ns3_built(ns3_dir, work)
    if error:
        print(error)
        for run in runs:
            row = _base_row(run, machine, software)
            row["mode"] = "speed"
            row["error"] = "build-failed"
            append_row(csv_path, row)
        return
    for run in runs:
        cfg = run
        for mode, realtime in (("speed", False), ("realtime", True)):
            log = results / f"ns3-{run['id']}-r{run['repeat']}-{mode}.log"
            timing = log.with_suffix(".timing") if realtime else None
            cmd = _ns3_command(
                ns3_dir,
                cfg,
                sim_time=float(run["sim_time_s"]),
                realtime=realtime,
                seed=int(run["seed"]),
                timing_log=timing,
                no_build=True,
                output_dir=work,
            )
            print(f"ns3 {run['id']} repeat {run['repeat']} {mode}", flush=True)
            code, wall, output = _run_process(
                cmd,
                cwd=ns3_dir,
                timeout=max(180.0, float(run["sim_time_s"]) * 80 + 30),
            )
            log.write_text(output)
            row = _base_row(run, machine, software)
            row["mode"] = mode
            row["sim_s"] = run["sim_time_s"]
            row["wall_s"] = round(wall, 3)
            if code != 0:
                row["error"] = f"exit-{code}"
            elif not realtime and wall > 0:
                row["speed_factor"] = round(float(run["sim_time_s"]) / wall, 4)
            if timing is not None:
                lags = parse_ns3_timing_log(timing)
                if lags:
                    row["lag_p99"] = round(percentile(lags, 99), 4)
                    row["lag_mean"] = round(sum(lags) / len(lags), 4)
            append_row(csv_path, row)


def _gz_factors(world: Path, duration: float, model_path: str, prefix: list[str] | None = None) -> list[float]:
    env = os.environ.copy()
    if model_path:
        env["GAZEBO_MODEL_PATH"] = model_path
    cmd = list(prefix or []) + ["gzserver", "--verbose", str(world)]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        stats = subprocess.run(
            ["gz", "stats", "-p", "-d", str(int(duration))],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=duration + 30,
            check=False,
        )
        return parse_gz_stats_factors(stats.stdout or "")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def start_velocity_publishers(robot_count: int) -> subprocess.Popen | None:
    if robot_count <= 0 or not shutil.which("ros2"):
        return None
    topics = ["/cmd_vel"] + [f"/robot{i}/cmd_vel" for i in range(robot_count)]
    pubs = " ".join(
        f"ros2 topic pub -r 5 {topic} geometry_msgs/msg/Twist \"{{linear: {{x: 0.2}}}}\" >/dev/null 2>&1 &"
        for topic in topics
    )
    script = f"source /opt/ros/humble/setup.bash && {pubs} wait"
    return subprocess.Popen(["bash", "-lc", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_gazebo_suite(runs: list[dict[str, Any]], results: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    machine = machine_info()
    software = software_info(find_ns3_dir())
    csv_path = results / "results.csv"
    if not shutil.which("gzserver"):
        print("skipping gazebo suite: gzserver not found")
        return
    announced: set[str] = set()
    for run in runs:
        kind = str(run["world"])
        if kind != "empty" and resolve_world(kind) is None:
            if kind not in announced:
                print(
                    f"skipping gazebo world {kind}: not found "
                    "(set CORNET_SMALL_WAREHOUSE or CORNET_LARGE_WAREHOUSE)"
                )
                announced.add(kind)
            row = _base_row(run, machine, software)
            row["mode"] = "skipped"
            row["error"] = "skipped-missing-world"
            append_row(csv_path, row)
            continue
        for mode, rate in (("max_speed", 0), ("default_rtf", 1000)):
            world_path = results / "worlds" / f"{run['id']}-r{run['repeat']}-{mode}.sdf"
            generated = generate_world(
                world_path,
                world=kind,
                robots=int(run["robots"]),
                actors=int(run["actors"]),
                camera=bool(run["camera"]),
                step_ms=float(run["step_ms"]),
                update_rate=rate,
            )
            if generated is None:
                continue
            source = resolve_world(kind) if kind != "empty" else None
            factors = _gz_factors(
                generated,
                float(run["duration_s"]),
                model_path_for(source),
            )
            summary = _stats(factors)
            row = _base_row(run, machine, software)
            row["mode"] = mode
            row["wall_s"] = run["duration_s"]
            if summary:
                row["speed_factor"] = round(summary["mean"], 4) if mode == "max_speed" else ""
                row["rtf_mean"] = round(summary["mean"], 4)
                row["rtf_p5"] = round(summary["p5"], 4)
                row["rtf_min_sample"] = round(summary["min"], 4)
            else:
                row["error"] = "no-gz-stats"
            append_row(csv_path, row)


def measure_gz_stats_overhead(results: Path, duration: float = 8.0) -> dict[str, float]:
    """Compare an empty world with and without a parallel ``gz stats -p`` sampler."""
    if not shutil.which("gzserver"):
        print("gz stats overhead control skipped: gzserver not found")
        return {}
    world = results / "worlds" / "overhead.sdf"
    generate_world(world, world="empty", robots=0, actors=0, camera=False, step_ms=1, update_rate=1000)
    plain = _gz_factors(world, duration, model_path_for(None))
    env = os.environ.copy()
    env["GAZEBO_MODEL_PATH"] = model_path_for(None)
    proc = subprocess.Popen(
        ["gzserver", str(world)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sampler = subprocess.Popen(
        ["gz", "stats", "-p"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1.5)
        sampled = subprocess.run(
            ["gz", "stats", "-p", "-d", str(int(duration))],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=duration + 30,
            check=False,
        )
        sampled_factors = parse_gz_stats_factors(sampled.stdout or "")
    finally:
        sampler.terminate()
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
    report = {
        "plain_rtf_mean": _stats(plain).get("mean", 0.0),
        "sampled_rtf_mean": _stats(sampled_factors).get("mean", 0.0),
    }
    if report["plain_rtf_mean"]:
        report["overhead"] = report["plain_rtf_mean"] - report["sampled_rtf_mean"]
    path = results / "gz_stats_overhead.json"
    path.write_text(__import__("json").dumps(report, indent=2) + "\n")
    print(f"gz stats overhead control: {report}")
    return report


def _pin_prefix(enabled: bool, core: int) -> list[str]:
    if not enabled:
        return []
    cores = os.cpu_count() or 1
    if cores < 2 or not shutil.which("taskset"):
        print("skipping CPU pinning: need taskset and at least 2 cores")
        return []
    return ["taskset", "-c", str(core % cores)]


def run_combined_suite(runs: list[dict[str, Any]], results: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    ns3_dir = find_ns3_dir()
    machine = machine_info()
    software = software_info(ns3_dir)
    csv_path = results / "results.csv"
    if ns3_dir is None or not shutil.which("gzserver"):
        print("skipping combined suite: NS-3 or gzserver missing")
        return
    work = results / "ns3-build"
    work.mkdir(parents=True, exist_ok=True)
    error = ensure_ns3_built(ns3_dir, work)
    if error:
        print(error)
        return
    for run in runs:
        if run.get("tap") and not has_cap_net_admin():
            print(f"skipping TAP variant {run['name']} repeat {run['repeat']}: CAP_NET_ADMIN unavailable")
            row = _base_row(run, machine, software)
            row["mode"] = "combined"
            row["tap_status"] = "skipped"
            append_row(csv_path, row)
            continue
        kind = run["gazebo"]["world"]
        if kind != "empty" and resolve_world(kind) is None:
            print(f"skipping combined world {kind}: not found")
            row = _base_row(run, machine, software)
            row["mode"] = "combined"
            row["error"] = "skipped-missing-world"
            append_row(csv_path, row)
            continue
        world_path = results / "worlds" / f"combined-{run['name']}-r{run['repeat']}.sdf"
        generated = generate_world(
            world_path,
            world=kind,
            robots=int(run["gazebo"]["robots"]),
            actors=int(run["gazebo"]["actors"]),
            camera=bool(run["gazebo"]["camera"]),
            step_ms=float(run["gazebo"]["step_ms"]),
            update_rate=1000,
        )
        if generated is None:
            continue
        timing = results / f"combined-{run['name']}-r{run['repeat']}.timing"
        duration = float(run["duration_s"])
        tun = None
        tap_status = ""
        if run.get("tap"):
            from cornet.middleware import TunManager

            tun = TunManager(ip_list=["10.254.0.1"])
            tun.setup()
            tap_status = "tun-setup"
        ns3_prefix = _pin_prefix(bool(run.get("pin_cpu")), 0)
        gz_prefix = _pin_prefix(bool(run.get("pin_cpu")), 1)
        ns3_cmd = _ns3_command(
            ns3_dir,
            run["ns3"],
            sim_time=float(run["sim_time_s"]),
            realtime=True,
            seed=int(run["seed"]),
            timing_log=timing,
            no_build=True,
            output_dir=work,
            prefix=ns3_prefix,
        )
        env = os.environ.copy()
        source = resolve_world(kind) if kind != "empty" else None
        env["GAZEBO_MODEL_PATH"] = model_path_for(source)
        gz_cmd = gz_prefix + ["gzserver", str(generated)]
        gz_proc = subprocess.Popen(gz_cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        drive = start_velocity_publishers(int(run["gazebo"]["robots"]))
        code, wall, _out = _run_process(ns3_cmd, cwd=ns3_dir, timeout=duration * 30 + 60)
        stats = subprocess.run(
            ["gz", "stats", "-p", "-d", "2"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        factors = parse_gz_stats_factors(stats.stdout or "")
        if drive is not None and drive.poll() is None:
            drive.terminate()
        if gz_proc.poll() is None:
            gz_proc.terminate()
            try:
                gz_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                gz_proc.kill()
        if tun is not None:
            tun.teardown()
        summary = _stats(factors)
        lags = parse_ns3_timing_log(timing)
        row = _base_row(run, machine, software)
        row["mode"] = "combined"
        row["tap_status"] = tap_status
        row["sim_s"] = run["sim_time_s"]
        row["wall_s"] = round(wall, 3)
        if code != 0:
            row["error"] = f"exit-{code}"
        if summary:
            row["rtf_mean"] = round(summary["mean"], 4)
            row["rtf_p5"] = round(summary["p5"], 4)
            row["rtf_min_sample"] = round(summary["min"], 4)
        if lags:
            row["lag_p99"] = round(percentile(lags, 99), 4)
            row["lag_mean"] = round(sum(lags) / len(lags), 4)
        append_row(csv_path, row)


def execute(suite: str, *, quick: bool, dry_run: bool, results: Path | None = None) -> Path:
    names = ["ns3", "gazebo", "combined"] if suite == "all" else [suite]
    runs = expand_suite(suite, quick=quick)
    if dry_run:
        print(format_dry_run(runs), end="")
        return results or Path("bench_results")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = results or (Path("bench_results") / stamp)
    dest.mkdir(parents=True, exist_ok=True)
    if "gazebo" in names or suite == "all":
        measure_gz_stats_overhead(dest)
    for name in names:
        selected = [run for run in runs if run["suite"] == name]
        if name == "ns3":
            run_ns3_suite(selected, dest, dry_run=False)
        elif name == "gazebo":
            run_gazebo_suite(selected, dest, dry_run=False)
        else:
            run_combined_suite(selected, dest, dry_run=False)
    rows = read_rows(dest / "results.csv")
    write_summary(dest, rows, classify_rows(rows))
    print(f"results: {dest}")
    return dest
