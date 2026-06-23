"""
SWIFT Processing System - Metrics Dashboard

Run with: streamlit run dashboard.py
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

METRICS_FILE = Path("audits/metrics.jsonl")


def load_metrics():
    """Load all metrics runs from the JSONL file."""
    if not METRICS_FILE.exists():
        return []
    records = []
    with open(METRICS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_runs_df(records):
    """Build a summary DataFrame across all runs."""
    rows = []
    for r in records:
        perf = r.get("performance", {})
        eff = r.get("efficiency", {})
        ops = r.get("operations", {})
        eo = ops.get("evaluator_optimizer", {})
        par = ops.get("parallelization", {})
        pc_decisions = ops.get("prompt_chaining", {}).get("decisions", {})

        rows.append({
            "run_id": r["run_id"][:8],
            "timestamp": r["timestamp"],
            "total_time_s": perf.get("total_pipeline_time_seconds", 0),
            "throughput": perf.get("overall_throughput_msgs_per_sec", 0),
            "total_messages": perf.get("total_messages", 0),
            "llm_calls": eff.get("total_llm_calls", 0),
            "total_tokens": eff.get("total_tokens", 0),
            "cost_usd": eff.get("estimated_cost_usd", 0),
            "cost_per_msg": eff.get("cost_per_message_usd", 0),
            "retries": eff.get("total_retries", 0),
            "stp_rate": eo.get("stp_rate", 0),
            "manual_repair_rate": eo.get("manual_repair_rate", 0),
            "fraud_flag_rate": par.get("fraud_flag_rate", 0),
            "approved": pc_decisions.get("APPROVE", 0),
            "held": pc_decisions.get("HOLD", 0),
            "rejected": pc_decisions.get("REJECT", 0),
        })
    return pd.DataFrame(rows)


def render_performance(records, runs_df):
    st.header("Performance Metrics")

    latest = records[-1]
    perf = latest["performance"]
    steps = perf.get("steps", {})

    # Top-level KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pipeline Time", f"{perf['total_pipeline_time_seconds']:.1f}s")
    col2.metric("Throughput", f"{perf['overall_throughput_msgs_per_sec']:.3f} msg/s")
    col3.metric("Messages Processed", perf["total_messages"])

    # Step duration bar chart
    step_df = pd.DataFrame([
        {"Step": step, "Duration (s)": data["duration_seconds"],
         "Throughput (msg/s)": data["throughput_msgs_per_sec"]}
        for step, data in steps.items()
    ])

    col_left, col_right = st.columns(2)

    with col_left:
        fig = px.bar(step_df, x="Step", y="Duration (s)",
                     title="Duration per Pipeline Step",
                     color="Step", text_auto=".2f")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig = px.bar(step_df, x="Step", y="Throughput (msg/s)",
                     title="Throughput per Pipeline Step",
                     color="Step", text_auto=".3f")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Historical throughput trend
    if len(runs_df) > 1:
        st.subheader("Throughput Trend Across Runs")
        fig = px.line(runs_df, x="timestamp", y="throughput",
                      markers=True, title="Overall Throughput Over Time")
        fig.update_xaxes(title="Run Timestamp")
        fig.update_yaxes(title="Messages / Second")
        st.plotly_chart(fig, use_container_width=True)

    # Historical pipeline time trend
    if len(runs_df) > 1:
        st.subheader("Pipeline Time Trend")
        fig = px.line(runs_df, x="timestamp", y="total_time_s",
                      markers=True, title="Total Pipeline Time Over Time")
        fig.update_xaxes(title="Run Timestamp")
        fig.update_yaxes(title="Seconds")
        st.plotly_chart(fig, use_container_width=True)


def render_efficiency(records, runs_df):
    st.header("Efficiency Metrics")

    latest = records[-1]
    eff = latest["efficiency"]

    # Top-level KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total LLM Calls", eff["total_llm_calls"])
    col2.metric("Total Tokens", f"{eff['total_tokens']:,}")
    col3.metric("Estimated Cost", f"${eff['estimated_cost_usd']:.4f}")
    col4.metric("Cost per Message", f"${eff['cost_per_message_usd']:.4f}")

    col_extra1, col_extra2 = st.columns(2)
    col_extra1.metric("Prompt Tokens", f"{eff['total_prompt_tokens']:,}")
    col_extra2.metric("Completion Tokens", f"{eff['total_completion_tokens']:,}")

    # Token distribution by step (pie chart)
    breakdown = eff.get("step_breakdown", {})
    token_data = [
        {"Step": step, "Tokens": data["prompt_tokens"] + data["completion_tokens"]}
        for step, data in breakdown.items()
    ]

    col_left, col_right = st.columns(2)

    with col_left:
        fig = px.pie(pd.DataFrame(token_data), values="Tokens", names="Step",
                     title="Token Distribution by Step")
        st.plotly_chart(fig, use_container_width=True)

    # LLM calls & retries by step (bar chart)
    with col_right:
        calls_data = pd.DataFrame([
            {"Step": step, "LLM Calls": data["llm_calls"], "Retries": data["retries"]}
            for step, data in breakdown.items()
        ])
        fig = px.bar(calls_data, x="Step", y=["LLM Calls", "Retries"],
                     title="LLM Calls & Retries by Step", barmode="group",
                     text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    # Cost breakdown table
    st.subheader("Cost Breakdown by Step")
    cost_rows = []
    for step, data in breakdown.items():
        input_cost = data["prompt_tokens"] / 1_000_000 * 2.50
        output_cost = data["completion_tokens"] / 1_000_000 * 10.00
        cost_rows.append({
            "Step": step,
            "LLM Calls": data["llm_calls"],
            "Prompt Tokens": data["prompt_tokens"],
            "Completion Tokens": data["completion_tokens"],
            "Input Cost ($)": round(input_cost, 6),
            "Output Cost ($)": round(output_cost, 6),
            "Total Cost ($)": round(input_cost + output_cost, 6),
            "Retries": data["retries"],
        })
    st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)

    # Historical cost trend
    if len(runs_df) > 1:
        st.subheader("Cost Trend Across Runs")
        fig = px.line(runs_df, x="timestamp", y="cost_usd",
                      markers=True, title="Estimated Cost Over Time")
        fig.update_xaxes(title="Run Timestamp")
        fig.update_yaxes(title="Cost (USD)")
        st.plotly_chart(fig, use_container_width=True)


def render_operations(records, runs_df):
    st.header("Operations Metrics")

    latest = records[-1]
    ops = latest["operations"]
    eo = ops.get("evaluator_optimizer", {})
    par = ops.get("parallelization", {})
    pc = ops.get("prompt_chaining", {})
    ow = ops.get("orchestrator_worker", {})

    # Top-level KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("STP Rate", f"{eo.get('stp_rate', 0) * 100:.1f}%")
    col2.metric("Manual Repair Rate", f"{eo.get('manual_repair_rate', 0) * 100:.1f}%")
    col3.metric("Fraud Flag Rate", f"{par.get('fraud_flag_rate', 0) * 100:.1f}%")

    # Message pipeline funnel
    st.subheader("Message Pipeline Funnel")
    total = eo.get("total", 0)
    valid = eo.get("valid", 0)
    clean = par.get("clean", 0)
    decisions = pc.get("decisions", {})
    approved = decisions.get("APPROVE", 0)

    funnel_data = pd.DataFrame({
        "Stage": ["Generated", "Valid (post-eval)", "Clean (non-fraud)", "Approved (final)"],
        "Messages": [total, valid, clean, approved],
    })
    fig = go.Figure(go.Funnel(
        y=funnel_data["Stage"],
        x=funnel_data["Messages"],
        textinfo="value+percent initial",
    ))
    fig.update_layout(title="Message Flow Through Pipeline")
    st.plotly_chart(fig, use_container_width=True)

    # Final decisions breakdown
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Final Decisions (Prompt Chaining)")
        dec_df = pd.DataFrame([
            {"Decision": k, "Count": v}
            for k, v in decisions.items()
        ])
        if not dec_df.empty:
            fig = px.pie(dec_df, values="Count", names="Decision",
                         title="Final Decision Distribution",
                         color="Decision",
                         color_discrete_map={"APPROVE": "#2ecc71", "HOLD": "#f39c12", "REJECT": "#e74c3c"})
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Orchestrator Task Distribution")
        ow_df = pd.DataFrame([
            {"Run": "Run 1 (Non-Fraud)", "Groups": ow.get("run_1_groups", 0), "Tasks": ow.get("run_1_tasks", 0)},
            {"Run": "Run 2 (High-Value)", "Groups": ow.get("run_2_groups", 0), "Tasks": ow.get("run_2_tasks", 0)},
        ])
        fig = px.bar(ow_df, x="Run", y=["Groups", "Tasks"],
                     title="Orchestrator Groups & Tasks", barmode="group", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    # Historical STP & fraud rate trends
    if len(runs_df) > 1:
        st.subheader("Operational Trends Across Runs")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=runs_df["timestamp"], y=runs_df["stp_rate"] * 100,
                                 mode="lines+markers", name="STP Rate (%)"))
        fig.add_trace(go.Scatter(x=runs_df["timestamp"], y=runs_df["fraud_flag_rate"] * 100,
                                 mode="lines+markers", name="Fraud Flag Rate (%)"))
        fig.add_trace(go.Scatter(x=runs_df["timestamp"], y=runs_df["manual_repair_rate"] * 100,
                                 mode="lines+markers", name="Manual Repair Rate (%)"))
        fig.update_layout(title="Operational Rates Over Time",
                          xaxis_title="Run Timestamp", yaxis_title="Rate (%)")
        st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(page_title="SWIFT Processing Metrics", layout="wide")
    st.title("SWIFT Processing System - Metrics Dashboard")

    records = load_metrics()

    if not records:
        st.warning("No metrics data found. Run the pipeline first: `python main.py`")
        return

    runs_df = build_runs_df(records)

    # Run selector
    st.sidebar.header("Run Selector")
    run_labels = [f"{r['run_id'][:8]} - {r['timestamp']}" for r in records]
    selected_idx = st.sidebar.selectbox(
        "Select a run to inspect",
        range(len(records)),
        index=len(records) - 1,
        format_func=lambda i: run_labels[i],
    )
    records_view = [records[selected_idx]]

    tab1, tab2, tab3 = st.tabs(["Performance", "Efficiency", "Operations"])

    with tab1:
        render_performance(records_view, runs_df)

    with tab2:
        render_efficiency(records_view, runs_df)

    with tab3:
        render_operations(records_view, runs_df)

    # Raw data expander
    with st.expander("Raw Metrics JSON"):
        st.json(records_view[0])


if __name__ == "__main__":
    main()
