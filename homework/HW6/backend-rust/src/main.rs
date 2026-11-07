use axum::{routing::get, Json, Router, extract::Query};
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, net::SocketAddr};
use tower_http::cors::CorsLayer;
use chrono::Utc;

#[derive(Serialize)]
struct Health { service: String, status: String, time: String }

#[derive(Deserialize)]
struct FibParams { n: Option<u64> }

#[derive(Serialize)]
struct FibResult { service: String, n: u64, fibonacci: u64, time_ms: u128 }

fn fib(n: u64) -> u64 {
    let (mut a, mut b) = (0u64, 1u64);
    for _ in 0..n { let t = a.wrapping_add(b); a = b; b = t; }
    a
}

async fn health() -> Json<Health> {
    Json(Health { service: "rust".into(), status: "ok".into(), time: Utc::now().to_rfc3339() })
}

async fn hello() -> Json<HashMap<String, String>> {
    let mut m = HashMap::new();
    m.insert("service".into(), "rust".into());
    m.insert("message".into(), "Hello from Rust (Axum)!".into());
    Json(m)
}

async fn fib_handler(Query(p): Query<FibParams>) -> Json<FibResult> {
    let n = p.n.unwrap_or(20).min(90);
    let t0 = std::time::Instant::now();
    let v = fib(n);
    Json(FibResult { service: "rust".into(), n, fibonacci: v, time_ms: t0.elapsed().as_millis() })
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/api/health", get(health))
        .route("/api/hello", get(hello))
        .route("/api/fib", get(fib_handler))
        .layer(CorsLayer::permissive());
    let addr = SocketAddr::from(([0, 0, 0, 0], 8000));
    println!("Rust service listening on {}", addr);
    axum::Server::bind(&addr).serve(app.into_make_service()).await.unwrap();
}
