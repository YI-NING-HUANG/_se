from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .config import DISTRIBUTIONS, PICKUP_MODES, SimulationConfig
from .optimization import OptimizationResult, optimize_staffing
from .simulation import (
    ScenarioResult,
    SimulationResult,
    aggregate_results,
    compare_windows,
    run_replications,
    run_simulation,
)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--arrival-rate",
        type=float,
        default=120.0,
        help="customer arrivals per hour (default: 120)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=120.0,
        help="planning horizon in minutes (default: 120)",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=10.0,
        help="warm-up minutes excluded from metrics (default: 10)",
    )
    parser.add_argument(
        "--order-windows",
        type=int,
        default=3,
        help="number of ordering windows (default: 3)",
    )
    parser.add_argument(
        "--order-mean",
        type=float,
        default=75.0,
        help="mean order service time in seconds (default: 75)",
    )
    parser.add_argument(
        "--order-dist",
        choices=DISTRIBUTIONS,
        default="exponential",
        help="order service-time distribution (default: exponential)",
    )
    parser.add_argument(
        "--pickup-mode",
        choices=PICKUP_MODES,
        default="shared",
        help="pickup layout: shared, per_window, or none (default: shared)",
    )
    parser.add_argument(
        "--pickup-servers",
        type=int,
        default=2,
        help="pickup servers for shared mode (default: 2)",
    )
    parser.add_argument(
        "--pickup-mean",
        type=float,
        default=45.0,
        help="mean pickup service time in seconds (default: 45)",
    )
    parser.add_argument(
        "--pickup-dist",
        choices=DISTRIBUTIONS,
        default="exponential",
        help="pickup service-time distribution (default: exponential)",
    )
    parser.add_argument(
        "--max-order-queue",
        type=int,
        default=None,
        help="balk when this many customers are already waiting to order",
    )
    parser.add_argument(
        "--max-pickup-queue",
        type=int,
        default=None,
        help="balk when this many customers are already waiting for pickup",
    )
    parser.add_argument(
        "--order-patience",
        type=float,
        default=None,
        help="mean order-queue patience in seconds (default: infinite)",
    )
    parser.add_argument(
        "--pickup-patience",
        type=float,
        default=None,
        help="mean pickup-queue patience in seconds (default: infinite)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="random seed for the first replication (default: 42)",
    )


def _build_config(args: argparse.Namespace) -> SimulationConfig:
    return SimulationConfig(
        arrival_rate_per_hour=args.arrival_rate,
        duration_minutes=args.duration,
        warmup_minutes=args.warmup,
        order_windows=args.order_windows,
        order_mean_s=args.order_mean,
        order_dist=args.order_dist,
        pickup_mode=args.pickup_mode,
        pickup_servers=args.pickup_servers,
        pickup_mean_s=args.pickup_mean,
        pickup_dist=args.pickup_dist,
        max_order_queue=args.max_order_queue,
        max_pickup_queue=args.max_pickup_queue,
        order_patience_mean_s=args.order_patience,
        pickup_patience_mean_s=args.pickup_patience,
        seed=args.seed,
    )


def _run(config: SimulationConfig, replications: int) -> SimulationResult:
    if replications == 1:
        return run_simulation(config)
    return aggregate_results(run_replications(config, replications))


def _format_seconds(value: float) -> str:
    return f"{value:,.1f}"


def _print_summary(result: SimulationResult) -> None:
    metrics = result.metrics
    print(
        f"觀察期間       : "
        f"{result.config.duration_minutes - result.config.warmup_minutes:.0f} 分鐘 "
        f"x {result.replications} 次模擬"
    )
    print(
        f"到達／完成     : {metrics['arrivals']:.0f} / {metrics['served']:.0f} 人"
    )
    print(
        f"放棄           : {metrics['abandoned']:.0f} 人 "
        f"(點餐 balk {metrics['balked']:.0f} / renege {metrics['reneged_order']:.0f}；"
        f"取餐 balk {metrics['balked_pickup']:.0f} / renege {metrics['reneged_pickup']:.0f})"
    )
    print(
        f"完成率／吞吐量 : {metrics['completion_rate'] * 100:.1f}% / "
        f"{metrics['throughput_per_hour']:.1f} 人/小時"
    )
    print(
        f"平均總等候     : {_format_seconds(metrics['total_wait_mean_s'])} 秒 "
        f"(P95 {_format_seconds(metrics['total_wait_p95_s'])} 秒)"
    )
    print(
        f"  點餐等候     : {_format_seconds(metrics['order_wait_mean_s'])} 秒 "
        f"(P95 {_format_seconds(metrics['order_wait_p95_s'])} 秒)"
    )
    print(
        f"  取餐等候     : {_format_seconds(metrics['pickup_wait_mean_s'])} 秒 "
        f"(P95 {_format_seconds(metrics['pickup_wait_p95_s'])} 秒)"
    )
    print(
        f"平均系統停留   : {_format_seconds(metrics['system_time_mean_s'])} 秒 "
        f"(P95 {_format_seconds(metrics['system_time_p95_s'])} 秒)"
    )
    print(
        f"使用率         : 點餐 {metrics['order_utilization'] * 100:.1f}% / "
        f"取餐 {metrics['pickup_utilization'] * 100:.1f}%"
    )
    print(
        f"平均排隊人數   : 點餐 {metrics['avg_order_queue']:.2f} 人 / "
        f"取餐 {metrics['avg_pickup_queue']:.2f} 人"
    )
    print(
        f"最大排隊人數   : 點餐 {metrics['max_order_queue']:.0f} 人 / "
        f"取餐 {metrics['max_pickup_queue']:.0f} 人"
    )


def _print_comparison(scenarios: list[ScenarioResult]) -> None:
    header = (
        f"{'Win':>4} {'Mean(s)':>10} {'P95(s)':>10} "
        f"{'Done%':>8} {'PerHour':>9} {'Order%':>9} {'Pickup%':>9} {'MaxQ':>6}"
    )
    print(header)
    print("-" * len(header))
    for scenario in scenarios:
        metrics = scenario.metrics
        print(
            f"{scenario.config.order_windows:>4} "
            f"{_format_seconds(metrics['total_wait_mean_s']):>10} "
            f"{_format_seconds(metrics['total_wait_p95_s']):>10} "
            f"{metrics['completion_rate'] * 100:>7.1f}% "
            f"{metrics['throughput_per_hour']:>9.1f} "
            f"{metrics['order_utilization'] * 100:>8.1f}% "
            f"{metrics['pickup_utilization'] * 100:>8.1f}% "
            f"{metrics['max_order_queue']:>9.0f}"
        )


def _print_optimization(result: OptimizationResult) -> None:
    targets = []
    if result.target_mean_wait_s is not None:
        targets.append(f"平均總等候 <= {result.target_mean_wait_s:.0f} 秒")
    if result.target_p95_wait_s is not None:
        targets.append(f"P95 總等候 <= {result.target_p95_wait_s:.0f} 秒")
    print("目標：" + "、".join(targets))
    print(f"模擬次數：每次配置 {result.replications} 次，取顧客等候時間池化後計算")
    print()

    best = result.best
    if best is None:
        print("找不到符合目標的人力配置；請放寬目標或提高上限。")
        print()
        print("等候時間最短的候選方案：")
        for candidate in sorted(
            result.candidates, key=lambda item: item.metrics["total_wait_mean_s"]
        )[:3]:
            print(
                f"  窗數 {candidate.order_windows}、取餐檯 {candidate.pickup_servers}："
                f"平均 {_format_seconds(candidate.metrics['total_wait_mean_s'])} 秒、"
                f"P95 {_format_seconds(candidate.metrics['total_wait_p95_s'])} 秒、"
                f"成本 {candidate.hourly_cost:,.0f} 元/小時"
            )
        return

    print(
        f"最佳方案：點餐窗口 {best.order_windows} 個、取餐檯 {best.pickup_servers} 個，"
        f"成本 {best.hourly_cost:,.0f} 元/小時"
    )
    print(
        f"  平均總等候 {_format_seconds(best.metrics['total_wait_mean_s'])} 秒、"
        f"P95 {_format_seconds(best.metrics['total_wait_p95_s'])} 秒、"
        f"完成率 {best.metrics['completion_rate'] * 100:.1f}%"
    )
    print()
    print("可行候選方案（依成本排序）：")
    header = (
        f"{'Win':>4} {'Pickup':>7} {'Cost/h':>10} "
        f"{'Mean(s)':>10} {'P95(s)':>10} {'Done%':>8}"
    )
    print(header)
    print("-" * len(header))
    for candidate in result.ranked()[:8]:
        print(
            f"{candidate.order_windows:>4} {candidate.pickup_servers:>6} "
            f"{candidate.hourly_cost:>10,.0f} "
            f"{_format_seconds(candidate.metrics['total_wait_mean_s']):>10} "
            f"{_format_seconds(candidate.metrics['total_wait_p95_s']):>10} "
            f"{candidate.metrics['completion_rate'] * 100:>7.1f}%"
        )


def _cmd_run(args: argparse.Namespace) -> int:
    config = _build_config(args)
    result = _run(config, args.replications)
    if args.json:
        payload = {
            "config": asdict(config),
            "replications": result.replications,
            "metrics": result.metrics,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("== 學餐排隊模擬 ==")
        _print_summary(result)
    return 0


def _window_list(value: str) -> list[int]:
    try:
        counts = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "use comma-separated integers, for example 1,2,3,4"
        ) from exc
    if not counts or any(count < 1 for count in counts):
        raise argparse.ArgumentTypeError("window counts must be integers >= 1")
    return counts


def _cmd_compare(args: argparse.Namespace) -> int:
    config = _build_config(args)
    scenarios = compare_windows(config, args.windows, args.replications)
    if args.json:
        payload = {
            "config": asdict(config),
            "replications": args.replications,
            "scenarios": [scenario.to_dict() for scenario in scenarios],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("== 加開點餐窗口的情境比較 ==")
        print(
            f"到達率 {config.arrival_rate_per_hour:.0f} 人/小時、"
            f"取餐模式 {config.pickup_mode}、取餐檯 {config.pickup_servers} 個、"
            f"每次情境 {args.replications} 次模擬"
        )
        print()
        _print_comparison(scenarios)
    return 0


def _cmd_optimize(args: argparse.Namespace) -> int:
    if args.target_mean_wait is None and args.target_p95_wait is None:
        args.target_mean_wait = 180.0
    config = _build_config(args)
    result = optimize_staffing(
        config,
        max_order_windows=args.max_order_windows,
        max_pickup_servers=args.max_pickup_servers,
        order_window_cost=args.order_cost,
        pickup_server_cost=args.pickup_cost,
        target_mean_wait_s=args.target_mean_wait,
        target_p95_wait_s=args.target_p95_wait,
        replications=args.replications,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("== 最低成本人力配置 ==")
        _print_optimization(result)
    return 0 if result.best is not None else 1


def _cmd_demo(args: argparse.Namespace) -> int:
    base = SimulationConfig(
        arrival_rate_per_hour=120.0,
        duration_minutes=120.0,
        warmup_minutes=10.0,
        order_windows=3,
        order_mean_s=75.0,
        order_dist="exponential",
        pickup_mode="shared",
        pickup_servers=2,
        pickup_mean_s=45.0,
        pickup_dist="exponential",
        seed=7,
    )
    scenarios = compare_windows(base, [1, 2, 3, 4, 5], replications=3)
    result = optimize_staffing(
        base,
        max_order_windows=6,
        max_pickup_servers=4,
        order_window_cost=150.0,
        pickup_server_cost=100.0,
        target_mean_wait_s=180.0,
        target_p95_wait_s=450.0,
        replications=3,
    )

    print("== cafeteria-sim 示範：午餐尖峰 ==")
    print(
        "情境：每小時 120 人到達；點餐平均 75 秒；共用取餐區、"
        "每個取餐檯平均 45 秒；模擬 2 小時，前 10 分鐘暖機。"
    )
    print()
    print("1) 只加開點餐窗口，取餐人力固定 2 人")
    _print_comparison(scenarios)
    print()
    print("2) 以平均等候 <= 180 秒、P95 <= 450 秒為目標，尋找最低成本配置")
    print("   成本假設：點餐窗口 150 元/小時、取餐檯 100 元/小時")
    print()
    _print_optimization(result)
    print()
    print("完成：套件已可執行模擬、情境比較與人力最佳化。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cafeteria-sim",
        description=(
            "Discrete-event simulation and staffing optimization for "
            "school cafeteria queues."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run one scenario")
    _add_common_options(run_parser)
    run_parser.add_argument(
        "--replications",
        type=int,
        default=1,
        help="number of independent replications (default: 1)",
    )
    run_parser.add_argument("--json", action="store_true", help="print JSON")
    run_parser.set_defaults(func=_cmd_run)

    compare_parser = subparsers.add_parser(
        "compare", help="compare different numbers of ordering windows"
    )
    _add_common_options(compare_parser)
    compare_parser.add_argument(
        "--windows",
        type=_window_list,
        default=[1, 2, 3, 4, 5],
        help="comma-separated window counts to compare (default: 1,2,3,4,5)",
    )
    compare_parser.add_argument(
        "--replications",
        type=int,
        default=3,
        help="number of independent replications per scenario (default: 3)",
    )
    compare_parser.add_argument("--json", action="store_true", help="print JSON")
    compare_parser.set_defaults(func=_cmd_compare)

    optimize_parser = subparsers.add_parser(
        "optimize", help="find the cheapest staffing plan that meets a wait target"
    )
    _add_common_options(optimize_parser)
    optimize_parser.add_argument(
        "--target-mean-wait",
        type=float,
        default=None,
        help="maximum mean total waiting time in seconds (default: 180)",
    )
    optimize_parser.add_argument(
        "--target-p95-wait",
        type=float,
        default=None,
        help="maximum p95 total waiting time in seconds",
    )
    optimize_parser.add_argument(
        "--max-order-windows",
        type=int,
        default=6,
        help="largest number of ordering windows to consider (default: 6)",
    )
    optimize_parser.add_argument(
        "--max-pickup-servers",
        type=int,
        default=4,
        help="largest number of pickup servers to consider (default: 4)",
    )
    optimize_parser.add_argument(
        "--order-cost",
        type=float,
        default=150.0,
        help="hourly cost of one ordering window (default: 150)",
    )
    optimize_parser.add_argument(
        "--pickup-cost",
        type=float,
        default=100.0,
        help="hourly cost of one pickup server (default: 100)",
    )
    optimize_parser.add_argument(
        "--replications",
        type=int,
        default=3,
        help="number of independent replications per plan (default: 3)",
    )
    optimize_parser.add_argument("--json", action="store_true", help="print JSON")
    optimize_parser.set_defaults(func=_cmd_optimize)

    demo_parser = subparsers.add_parser(
        "demo", help="run the built-in lunch-peak demonstration"
    )
    demo_parser.set_defaults(func=_cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
