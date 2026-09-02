//! Fail-closed lease enforcement for the fleet control plane.
//!
//! Mirrors the runner state machine defined in `src/mfm/model.py`: this crate
//! does not own the model, it enforces one invariant against it — a runner
//! that has missed its lease deadline is removed from scheduling before any
//! recovery path runs. See "Fail closed" in the README's design principles.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RunnerState {
    Ready,
    Leased,
    Draining,
    Quarantined,
    Destroyed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Runner {
    pub runner_id: String,
    pub image: String,
    #[serde(default = "default_arch")]
    pub arch: String,
    pub state: RunnerState,
    #[serde(default)]
    pub job_id: Option<String>,
    #[serde(default)]
    pub lease_expires_at: Option<f64>,
}

fn default_arch() -> String {
    "arm64".to_string()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReapAction {
    Quarantined,
    Unchanged,
}

/// Apply the fail-closed rule to one runner: a `Leased` runner whose
/// `lease_expires_at` is at or before `now` is quarantined and its job/lease
/// fields are cleared. Every other state is left untouched — reaping only
/// removes runners from scheduling, it never recovers or reschedules them.
pub fn reap_one(runner: &mut Runner, now: f64) -> ReapAction {
    if runner.state != RunnerState::Leased {
        return ReapAction::Unchanged;
    }
    let expired = match runner.lease_expires_at {
        Some(expires_at) => expires_at <= now,
        None => true,
    };
    if !expired {
        return ReapAction::Unchanged;
    }
    runner.state = RunnerState::Quarantined;
    runner.job_id = None;
    runner.lease_expires_at = None;
    ReapAction::Quarantined
}

/// Apply [`reap_one`] to every runner in `fleet`, returning the IDs of the
/// runners it quarantined, in input order.
pub fn reap_fleet(fleet: &mut [Runner], now: f64) -> Vec<String> {
    fleet
        .iter_mut()
        .filter_map(|runner| match reap_one(runner, now) {
            ReapAction::Quarantined => Some(runner.runner_id.clone()),
            ReapAction::Unchanged => None,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn leased(id: &str, expires_at: Option<f64>) -> Runner {
        Runner {
            runner_id: id.to_string(),
            image: "macos-15-xcode-16".to_string(),
            arch: "arm64".to_string(),
            state: RunnerState::Leased,
            job_id: Some("job-1".to_string()),
            lease_expires_at: expires_at,
        }
    }

    #[test]
    fn expired_lease_is_quarantined() {
        let mut runner = leased("m1-01", Some(100.0));
        let action = reap_one(&mut runner, 200.0);
        assert_eq!(action, ReapAction::Quarantined);
        assert_eq!(runner.state, RunnerState::Quarantined);
        assert!(runner.job_id.is_none());
        assert!(runner.lease_expires_at.is_none());
    }

    #[test]
    fn lease_at_exact_deadline_is_quarantined() {
        let mut runner = leased("m1-01", Some(200.0));
        assert_eq!(reap_one(&mut runner, 200.0), ReapAction::Quarantined);
    }

    #[test]
    fn active_lease_is_untouched() {
        let mut runner = leased("m1-01", Some(300.0));
        let action = reap_one(&mut runner, 200.0);
        assert_eq!(action, ReapAction::Unchanged);
        assert_eq!(runner.state, RunnerState::Leased);
        assert_eq!(runner.job_id.as_deref(), Some("job-1"));
    }

    #[test]
    fn leased_without_expiry_is_treated_as_expired() {
        let mut runner = leased("m1-01", None);
        assert_eq!(reap_one(&mut runner, 200.0), ReapAction::Quarantined);
    }

    #[test]
    fn non_leased_states_are_never_reaped() {
        for state in [
            RunnerState::Ready,
            RunnerState::Draining,
            RunnerState::Quarantined,
            RunnerState::Destroyed,
        ] {
            let mut runner = Runner {
                runner_id: "m1-01".to_string(),
                image: "macos-15-xcode-16".to_string(),
                arch: "arm64".to_string(),
                state,
                job_id: None,
                lease_expires_at: Some(0.0),
            };
            assert_eq!(reap_one(&mut runner, 1_000_000.0), ReapAction::Unchanged);
            assert_eq!(runner.state, state);
        }
    }

    #[test]
    fn reap_fleet_returns_only_quarantined_ids_in_order() {
        let mut fleet = vec![
            leased("m1-01", Some(100.0)),
            Runner {
                runner_id: "m1-02".to_string(),
                image: "macos-15-xcode-16".to_string(),
                arch: "arm64".to_string(),
                state: RunnerState::Ready,
                job_id: None,
                lease_expires_at: None,
            },
            leased("m1-03", Some(400.0)),
            leased("m1-04", Some(50.0)),
        ];
        let quarantined = reap_fleet(&mut fleet, 200.0);
        assert_eq!(quarantined, vec!["m1-01".to_string(), "m1-04".to_string()]);
        assert_eq!(fleet[2].state, RunnerState::Leased);
    }

    #[test]
    fn runner_round_trips_through_json_matching_python_cli_shape() {
        let json = r#"{
            "runner_id": "m1-01",
            "image": "macos-15-xcode-16",
            "arch": "arm64",
            "state": "leased",
            "job_id": "demo-123",
            "lease_expires_at": 100.5
        }"#;
        let runner: Runner = serde_json::from_str(json).expect("valid runner json");
        assert_eq!(runner.runner_id, "m1-01");
        assert_eq!(runner.state, RunnerState::Leased);

        let serialized = serde_json::to_string(&runner).expect("serializable runner");
        let round_tripped: Runner = serde_json::from_str(&serialized).expect("round trip");
        assert_eq!(round_tripped.runner_id, runner.runner_id);
        assert_eq!(round_tripped.state, runner.state);
    }
}
