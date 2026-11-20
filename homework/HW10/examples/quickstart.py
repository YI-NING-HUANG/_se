from cafeteria_sim import SimulationConfig, compare_windows, run_simulation


def main() -> None:
    config = SimulationConfig(
        arrival_rate_per_hour=120,
        duration_minutes=120,
        warmup_minutes=10,
        order_windows=3,
        order_mean_s=75,
        pickup_mode="shared",
        pickup_servers=2,
        pickup_mean_s=45,
        seed=42,
    )

    result = run_simulation(config)
    print(f"served={result.metrics['served']:.0f}")
    print(f"mean total wait={result.metrics['total_wait_mean_s']:.1f}s")
    print(f"p95 total wait={result.metrics['total_wait_p95_s']:.1f}s")

    print()
    for scenario in compare_windows(config, [2, 3, 4], replications=3):
        metrics = scenario.metrics
        print(
            f"{scenario.config.order_windows} windows: "
            f"mean={metrics['total_wait_mean_s']:.1f}s, "
            f"p95={metrics['total_wait_p95_s']:.1f}s, "
            f"served={metrics['served']:.0f}"
        )


if __name__ == "__main__":
    main()
