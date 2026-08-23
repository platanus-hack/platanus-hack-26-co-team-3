//! Deterministic attribute extraction from a request. This is data prep, NOT the
//! decision: it turns `action`/`payload`/`time` into typed attributes the DSL evaluates.

use crate::model::{ActionClassMap, CompiledPolicy, McpRequest, OpClass, Operation, WorkingHours};
use time::format_description::well_known::Rfc3339;
use time::{OffsetDateTime, UtcOffset};

#[derive(Clone, Debug)]
pub struct Attributes {
    /// Lowercased raw action.
    pub action: String,
    pub op_class: OpClass,
    pub collection: Option<String>,
    pub accessed_by: String,
    pub within_working_hours: bool,
}

/// Classify an action by the first matching keyword (case-insensitive). Unmatched → Unknown.
pub fn classify_action(action: &str, map: &ActionClassMap) -> OpClass {
    let a = action.to_lowercase();
    for (kw, class) in &map.keywords {
        if a.contains(&kw.to_lowercase()) {
            return *class;
        }
    }
    OpClass::Unknown
}

/// Whether `time_str` (RFC3339) falls inside the working-hours window, in the policy's tz.
pub fn within_working_hours(time_str: &str, wh: &WorkingHours) -> anyhow::Result<bool> {
    let dt = OffsetDateTime::parse(time_str, &Rfc3339)?;
    let offset = UtcOffset::from_whole_seconds(wh.tz_offset_minutes * 60)?;
    let local = dt.to_offset(offset);
    let dow = local.weekday().number_from_monday(); // Mon=1 … Sun=7
    if !wh.days.contains(&dow) {
        return Ok(false);
    }
    let minutes = local.hour() as u32 * 60 + local.minute() as u32;
    Ok(minutes >= wh.start_minute && minutes < wh.end_minute)
}

pub fn extract(
    req: &McpRequest,
    time_str: &str,
    policy: &CompiledPolicy,
) -> anyhow::Result<Attributes> {
    let collection = req
        .payload
        .get("collection")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    Ok(Attributes {
        action: req.action.to_lowercase(),
        op_class: classify_action(&req.action, &policy.action_classes),
        collection,
        accessed_by: req.accessed_by.clone(),
        within_working_hours: within_working_hours(time_str, &policy.working_hours)?,
    })
}

/// Build attributes for ONE operation: opClass + collection come from the normalizer
/// (semantic), while working-hours (`within`) and accessedBy stay deterministic/shared.
pub fn from_operation(op: &Operation, req: &McpRequest, within: bool) -> Attributes {
    Attributes {
        action: req.action.to_lowercase(),
        op_class: op.op_class,
        collection: op.collection.clone(),
        accessed_by: req.accessed_by.clone(),
        within_working_hours: within,
    }
}
