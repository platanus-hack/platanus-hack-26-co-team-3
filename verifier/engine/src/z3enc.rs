//! Z3 encoding of the policy — the decision kernel AND the policy prover.
//!
//! The SAME symbolic model is used two ways:
//!   - concretely (attributes fixed) → Z3 computes/certifies a single request's decision;
//!   - symbolically (attributes free) → Z3 proves properties over ALL possible requests
//!     (no-destructive-bypass, consistency, dead rules) — what a concrete evaluator can't do.
//!
//! Abstraction (finite, so proofs are decidable): opClass ∈ {0..5}; withinHours ∈ Bool;
//! collection ∈ {policy literals} ∪ {other}; each action literal / glob pattern used by the
//! policy is a Bool, with `action ⇒ opClass = classify(action)` coupling so proofs stay sound.

use crate::attributes::{classify_action, Attributes};
use crate::model::{CompiledPolicy, Condition, Effect, OpClass};
use std::collections::BTreeSet;
use z3::ast::{Bool, Int};
use z3::{SatResult, Solver};

fn opclass_index(c: OpClass) -> i64 {
    match c {
        OpClass::Read => 0,
        OpClass::Write => 1,
        OpClass::Destructive => 2,
        OpClass::Refund => 3,
        OpClass::Admin => 4,
        OpClass::Unknown => 5,
    }
}

fn opclass_from_index(i: i64) -> OpClass {
    match i {
        0 => OpClass::Read,
        1 => OpClass::Write,
        2 => OpClass::Destructive,
        3 => OpClass::Refund,
        4 => OpClass::Admin,
        _ => OpClass::Unknown,
    }
}

/// A concrete request Z3 produced as a counterexample.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RequestModel {
    pub op_class: OpClass,
    pub within_hours: bool,
    pub collection: Option<String>,
    /// Specific action literal Z3 chose, if any (else "some action of op_class").
    pub action_hint: Option<String>,
    pub accessed_by_hint: Option<String>,
    pub allowed: bool,
}

impl RequestModel {
    pub fn describe(&self) -> String {
        let act = self
            .action_hint
            .clone()
            .unwrap_or_else(|| format!("<some {:?} action>", self.op_class));
        let coll = self.collection.clone().unwrap_or_else(|| "<other/none>".into());
        format!(
            "{{action: {act}, opClass: {:?}, collection: {coll}, withinHours: {}}}",
            self.op_class, self.within_hours
        )
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Proof {
    /// UNSAT — the property holds for all requests.
    Holds,
    /// SAT — a concrete request that violates the property.
    Counterexample(RequestModel),
}

pub struct Enc<'p> {
    policy: &'p CompiledPolicy,
    coll_literals: Vec<String>,
    op_class: Int,
    within_hours: Bool,
    collection: Int,
    act: Vec<(String, Bool)>,
    globs: Vec<(String, Bool)>,
    rule_matches: Vec<Bool>,
    allowed_expr: Bool,
    /// Rule indices sorted by (priority asc, deny-before-allow) — the governing order.
    order: Vec<usize>,
}

impl<'p> Enc<'p> {
    pub fn new(policy: &'p CompiledPolicy) -> Self {
        // Collect literals used anywhere in conditions.
        let mut colls = BTreeSet::new();
        let mut acts = BTreeSet::new();
        let mut globs = BTreeSet::new();
        for r in &policy.rules {
            collect(&r.condition, &mut colls, &mut acts, &mut globs);
        }
        let coll_literals: Vec<String> = colls.into_iter().collect();
        let action_literals: Vec<String> = acts.into_iter().collect();
        let glob_patterns: Vec<String> = globs.into_iter().collect();

        let op_class = Int::new_const("op_class");
        let within_hours = Bool::new_const("within_hours");
        let collection = Int::new_const("collection");
        let act: Vec<(String, Bool)> = action_literals
            .iter()
            .map(|a| (a.clone(), Bool::new_const(format!("act_{a}"))))
            .collect();
        let globs: Vec<(String, Bool)> = glob_patterns
            .iter()
            .map(|g| (g.clone(), Bool::new_const(format!("glob_{g}"))))
            .collect();

        let mut enc = Enc {
            policy,
            coll_literals,
            op_class,
            within_hours,
            collection,
            act,
            globs,
            rule_matches: Vec::new(),
            allowed_expr: Bool::from_bool(false),
            order: Vec::new(),
        };

        enc.rule_matches = policy
            .rules
            .iter()
            .map(|r| enc.encode(&r.condition))
            .collect();

        // Governing order: priority asc, then Deny before Allow.
        let deny_rank = |e: Effect| if e == Effect::Deny { 0 } else { 1 };
        let mut order: Vec<usize> = (0..policy.rules.len()).collect();
        order.sort_by(|&a, &b| {
            policy.rules[a]
                .priority
                .cmp(&policy.rules[b].priority)
                .then(deny_rank(policy.rules[a].effect).cmp(&deny_rank(policy.rules[b].effect)))
        });
        enc.order = order;

        // allowed = first matching rule (in governing order) decides; else default.
        let mut acc = Bool::from_bool(policy.default_effect == Effect::Allow);
        for &i in enc.order.iter().rev() {
            let then = Bool::from_bool(policy.rules[i].effect == Effect::Allow);
            acc = enc.rule_matches[i].ite(&then, &acc);
        }
        enc.allowed_expr = acc;
        enc
    }

    fn coll_index(&self, name: &str) -> i64 {
        self.coll_literals
            .iter()
            .position(|c| c == name)
            .map(|i| i as i64)
            .unwrap_or(self.coll_literals.len() as i64)
    }

    fn act_bool(&self, name: &str) -> Bool {
        self.act
            .iter()
            .find(|(a, _)| a == name)
            .map(|(_, b)| b.clone())
            .unwrap_or_else(|| Bool::from_bool(false))
    }

    fn glob_bool(&self, pat: &str) -> Bool {
        self.globs
            .iter()
            .find(|(g, _)| g == pat)
            .map(|(_, b)| b.clone())
            .unwrap_or_else(|| Bool::from_bool(false))
    }

    fn encode(&self, c: &Condition) -> Bool {
        match c {
            Condition::Always => Bool::from_bool(true),
            Condition::Never => Bool::from_bool(false),
            Condition::OpClassIn { classes } => {
                let eqs: Vec<Bool> = classes
                    .iter()
                    .map(|k| self.op_class._eq(&Int::from_i64(opclass_index(*k))))
                    .collect();
                or_of(&eqs)
            }
            Condition::ActionEq { action } => self.act_bool(&action.to_lowercase()),
            Condition::CollectionEq { collection } => {
                self.collection._eq(&Int::from_i64(self.coll_index(collection)))
            }
            Condition::AccessedByGlob { pattern } => self.glob_bool(pattern),
            Condition::WithinWorkingHours => self.within_hours.clone(),
            Condition::OutsideWorkingHours => self.within_hours.not(),
            Condition::And { all } => {
                let v: Vec<Bool> = all.iter().map(|c| self.encode(c)).collect();
                and_of(&v)
            }
            Condition::Or { any } => {
                let v: Vec<Bool> = any.iter().map(|c| self.encode(c)).collect();
                or_of(&v)
            }
            Condition::Not { cond } => self.encode(cond).not(),
        }
    }

    /// Base well-formedness constraints on the symbolic request.
    fn base(&self) -> Vec<Bool> {
        let mut cs = vec![
            self.op_class.ge(&Int::from_i64(0)),
            self.op_class.le(&Int::from_i64(5)),
            self.collection.ge(&Int::from_i64(0)),
            self.collection
                .le(&Int::from_i64(self.coll_literals.len() as i64)),
        ];
        if !self.act.is_empty() {
            let pairs: Vec<(&Bool, i32)> = self.act.iter().map(|(_, b)| (b, 1)).collect();
            cs.push(Bool::pb_le(&pairs, 1)); // at most one action literal holds
            for (name, b) in &self.act {
                let idx = opclass_index(classify_action(name, &self.policy.action_classes));
                // act ⇒ opClass = classify(act)
                cs.push(or_of(&[b.not(), self.op_class._eq(&Int::from_i64(idx))]));
            }
        }
        cs
    }

    fn assert_base(&self, s: &Solver) {
        for c in self.base() {
            s.assert(&c);
        }
    }

    fn extract(&self, s: &Solver) -> RequestModel {
        let m = s.get_model().expect("model");
        let oc = m
            .eval(&self.op_class, true)
            .and_then(|v| v.as_i64())
            .unwrap_or(5);
        let wh = m
            .eval(&self.within_hours, true)
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let ci = m
            .eval(&self.collection, true)
            .and_then(|v| v.as_i64())
            .unwrap_or(self.coll_literals.len() as i64);
        let collection = self.coll_literals.get(ci as usize).cloned();
        let action_hint = self.act.iter().find_map(|(name, b)| {
            m.eval(b, true)
                .and_then(|v| v.as_bool())
                .filter(|&t| t)
                .map(|_| name.clone())
        });
        let accessed_by_hint = self.globs.iter().find_map(|(pat, b)| {
            m.eval(b, true)
                .and_then(|v| v.as_bool())
                .filter(|&t| t)
                .map(|_| format!("matches '{pat}'"))
        });
        let allowed = m
            .eval(&self.allowed_expr, true)
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        RequestModel {
            op_class: opclass_from_index(oc),
            within_hours: wh,
            collection,
            action_hint,
            accessed_by_hint,
            allowed,
        }
    }

    // ---- concrete decision (Z3 computes the verdict for one request) -------

    pub fn decide(&self, attrs: &Attributes) -> bool {
        let s = Solver::new();
        self.assert_base(&s);
        s.assert(&self.op_class._eq(&Int::from_i64(opclass_index(attrs.op_class))));
        s.assert(&bool_val(&self.within_hours, attrs.within_working_hours));
        let cidx = attrs
            .collection
            .as_deref()
            .map(|c| self.coll_index(c))
            .unwrap_or(self.coll_literals.len() as i64);
        s.assert(&self.collection._eq(&Int::from_i64(cidx)));
        for (name, b) in &self.act {
            s.assert(&bool_val(b, attrs.action == name.to_lowercase()));
        }
        for (pat, b) in &self.globs {
            s.assert(&bool_val(b, crate::dsl::eval(
                &Condition::AccessedByGlob { pattern: pat.clone() },
                attrs,
            )));
        }
        assert_eq!(s.check(), SatResult::Sat, "fixed request must be satisfiable");
        let m = s.get_model().expect("model");
        m.eval(&self.allowed_expr, true)
            .and_then(|v| v.as_bool())
            .expect("allowed value")
    }

    // ---- policy proofs (over ALL requests) ---------------------------------

    /// No request classified `destructive` can end up allowed.
    pub fn prove_no_destructive_bypass(&self) -> Proof {
        let s = Solver::new();
        self.assert_base(&s);
        s.assert(&self.op_class._eq(&Int::from_i64(opclass_index(OpClass::Destructive))));
        s.assert(&self.allowed_expr);
        match s.check() {
            SatResult::Unsat => Proof::Holds,
            SatResult::Sat => Proof::Counterexample(self.extract(&s)),
            SatResult::Unknown => panic!("Z3 unknown on a decidable finite query"),
        }
    }

    /// Same-priority contradictions: (rule_i, rule_j) same priority, opposite effect,
    /// with a request matching both. Returns the offending priorities + example.
    pub fn find_conflicts(&self) -> Vec<(i64, RequestModel)> {
        let rules = &self.policy.rules;
        let mut out = Vec::new();
        for i in 0..rules.len() {
            for j in (i + 1)..rules.len() {
                if rules[i].priority == rules[j].priority && rules[i].effect != rules[j].effect {
                    let s = Solver::new();
                    self.assert_base(&s);
                    s.assert(&self.rule_matches[i]);
                    s.assert(&self.rule_matches[j]);
                    if s.check() == SatResult::Sat {
                        out.push((rules[i].priority, self.extract(&s)));
                    }
                }
            }
        }
        out
    }

    /// Rule indices that can never govern (always shadowed by a higher-priority rule).
    pub fn find_dead_rules(&self) -> Vec<usize> {
        let pos: std::collections::HashMap<usize, usize> =
            self.order.iter().enumerate().map(|(p, &i)| (i, p)).collect();
        let mut dead = Vec::new();
        for i in 0..self.policy.rules.len() {
            let s = Solver::new();
            self.assert_base(&s);
            s.assert(&self.rule_matches[i]);
            // No rule that sorts before i may match (else it would govern instead).
            for (&k, &kp) in pos.iter() {
                if kp < pos[&i] {
                    s.assert(&self.rule_matches[k].not());
                }
            }
            if s.check() == SatResult::Unsat {
                dead.push(i);
            }
        }
        dead
    }
}

fn bool_val(b: &Bool, v: bool) -> Bool {
    if v {
        b.clone()
    } else {
        b.not()
    }
}

fn and_of(v: &[Bool]) -> Bool {
    if v.is_empty() {
        return Bool::from_bool(true);
    }
    let refs: Vec<&Bool> = v.iter().collect();
    Bool::and(&refs)
}

fn or_of(v: &[Bool]) -> Bool {
    if v.is_empty() {
        return Bool::from_bool(false);
    }
    let refs: Vec<&Bool> = v.iter().collect();
    Bool::or(&refs)
}

fn collect(
    c: &Condition,
    colls: &mut BTreeSet<String>,
    acts: &mut BTreeSet<String>,
    globs: &mut BTreeSet<String>,
) {
    match c {
        Condition::CollectionEq { collection } => {
            colls.insert(collection.clone());
        }
        Condition::ActionEq { action } => {
            acts.insert(action.to_lowercase());
        }
        Condition::AccessedByGlob { pattern } => {
            globs.insert(pattern.clone());
        }
        Condition::And { all } | Condition::Or { any: all } => {
            for x in all {
                collect(x, colls, acts, globs);
            }
        }
        Condition::Not { cond } => collect(cond, colls, acts, globs),
        _ => {}
    }
}
