//! `mfm-reaper` — sweep a fleet inventory snapshot and quarantine any runner
//! whose lease has expired.
//!
//! Reads a JSON array shaped like `mfm inventory sample`'s output (see
//! `src/mfm/cli.py`) from a file argument or stdin, applies the fail-closed
//! rule from `mfm_reaper::reap_fleet`, and writes the updated fleet back to
//! stdout as JSON. Exits `1` on malformed input so it fails closed in a
//! pipeline rather than silently passing bad data through.

use std::env;
use std::fs;
use std::io::{self, Read};
use std::process::ExitCode;
use std::time::{SystemTime, UNIX_EPOCH};

use mfm_reaper::{reap_fleet, Runner};

fn read_input(path: Option<&String>) -> io::Result<String> {
    match path {
        Some(path) => fs::read_to_string(path),
        None => {
            let mut buf = String::new();
            io::stdin().read_to_string(&mut buf)?;
            Ok(buf)
        }
    }
}

fn now_unix() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock is before the Unix epoch")
        .as_secs_f64()
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let path = args.get(1);

    let raw = match read_input(path) {
        Ok(raw) => raw,
        Err(err) => {
            eprintln!("mfm-reaper: failed to read input: {err}");
            return ExitCode::FAILURE;
        }
    };

    let mut fleet: Vec<Runner> = match serde_json::from_str(&raw) {
        Ok(fleet) => fleet,
        Err(err) => {
            eprintln!("mfm-reaper: invalid inventory JSON: {err}");
            return ExitCode::FAILURE;
        }
    };

    let quarantined = reap_fleet(&mut fleet, now_unix());
    for runner_id in &quarantined {
        eprintln!("mfm-reaper: quarantined {runner_id} (lease expired)");
    }

    match serde_json::to_string_pretty(&fleet) {
        Ok(json) => {
            println!("{json}");
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("mfm-reaper: failed to serialize fleet: {err}");
            ExitCode::FAILURE
        }
    }
}
