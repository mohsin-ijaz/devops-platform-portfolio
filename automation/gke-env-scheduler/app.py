"""Streamlit UI for Dev Environment Manager"""

import streamlit as st
import sys
import os

# Add controllers to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.orchestrator import Orchestrator
from controllers.streamlit_logger import StreamlitLogHandler, setup_streamlit_logging
import threading

# Setup logging for Streamlit
setup_streamlit_logging()

# Global flag to track if an operation is running
if 'operation_running' not in st.session_state:
    st.session_state.operation_running = False

# Page config
st.set_page_config(
    page_title="Dev Environment Manager",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize orchestrator
# Note: Using ttl to refresh config periodically (every 5 minutes)
@st.cache_resource(ttl=300)
def get_orchestrator():
    """Get orchestrator instance with 5-minute cache"""
    return Orchestrator()

# Show loading message while initializing
with st.spinner("🔄 Loading environment configurations... (30-60 seconds on first load over proxy)"):
    orch = get_orchestrator()
    environments = orch.list_environments()

# Main UI
st.title("🔧 Dev Environment Manager")
st.caption("Automated development environment management across multiple GCP projects")

# Debug: Show loaded environments count
if st.session_state.get('show_debug'):
    st.info(f"🔍 Debug: Loaded {len(environments)} environments: {', '.join(environments)}")

# Add cache clear button in sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🗑️ Clear Cache & Reload"):
        st.cache_resource.clear()
        st.success("Cache cleared!")
        st.rerun()
    
    if st.checkbox("Show Debug Info"):
        st.session_state.show_debug = True
    else:
        st.session_state.show_debug = False

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["🎛️ Control", "📊 Status", "⏰ Schedule", "📜 Logs"])

# ===== TAB 1: Control =====
with tab1:
    st.header("Environment Control")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("▶️ Start Environment")
        start_env = st.selectbox(
            "Select environment to start:",
            environments,
            key="start_select"
        )
        
        if st.button(f"▶️ Start {start_env}", use_container_width=True, type="primary"):
            # Clear logs before starting
            StreamlitLogHandler.clear_logs()

            with st.spinner(f"Starting {start_env}... This may take several minutes."):
                result = orch.start_environment(start_env)

                if result.get('success'):
                    st.success(f"✅ {result.get('message')}")

                    # Show steps
                    with st.expander("📋 Operation Details", expanded=True):
                        for step in result.get('steps', []):
                            step_name = step['step']
                            step_result = step['result']
                            if step_result.get('success'):
                                st.write(f"✅ {step_name}: {step_result.get('message', 'Success')}")
                            else:
                                st.write(f"❌ {step_name}: {step_result.get('error', 'Failed')}")
                else:
                    st.error(f"❌ {result.get('error', 'Failed to start environment')}")

                    # Show steps
                    with st.expander("📋 Operation Details", expanded=True):
                        for step in result.get('steps', []):
                            step_name = step['step']
                            step_result = step['result']
                            if step_result.get('success'):
                                st.write(f"✅ {step_name}")
                            else:
                                st.write(f"❌ {step_name}: {step_result.get('error')}")

            # Show detailed logs
            with st.expander("📜 Detailed Logs", expanded=False):
                logs = StreamlitLogHandler.get_logs_for_environment(start_env, max_lines=200)
                if logs:
                    for log in logs:
                        level = log['level']
                        msg = log['message']

                        # Color code by level
                        if level == 'ERROR':
                            st.markdown(f"<span style='color: red;'>🔴 {msg}</span>", unsafe_allow_html=True)
                        elif level == 'WARNING':
                            st.markdown(f"<span style='color: orange;'>🟡 {msg}</span>", unsafe_allow_html=True)
                        elif level == 'INFO':
                            st.text(f"ℹ️  {msg}")
                        else:
                            st.text(msg)
                else:
                    st.info("No logs captured for this operation")
    
    with col2:
        st.subheader("⏹️ Stop Environment")
        stop_env = st.selectbox(
            "Select environment to stop:",
            environments,
            key="stop_select"
        )
        
        if st.button(f"⏹️ Stop {stop_env}", use_container_width=True, type="secondary", disabled=st.session_state.operation_running):
            # Mark operation as running
            st.session_state.operation_running = True
            
            # Clear logs before starting
            StreamlitLogHandler.clear_logs()
            
            st.divider()
            st.subheader(f"🔄 Stopping {stop_env}")
            
            # Create expandable live log viewer
            with st.expander("📜 Live Operation Logs", expanded=True):
                log_display = st.empty()
                status_msg = st.empty()
            
            try:
                import threading
                import time
                
                operation_complete = threading.Event()
                operation_result = {}
                
                def run_stop():
                    result = orch.stop_environment(stop_env)
                    operation_result.update(result)
                    operation_complete.set()
                
                # Start operation in background
                op_thread = threading.Thread(target=run_stop, daemon=True)
                op_thread.start()
                
                # Update logs in real-time
                last_log_count = 0
                iteration = 0
                while not operation_complete.is_set():
                    logs = StreamlitLogHandler.get_logs(max_lines=200)
                    
                    if logs:
                        with log_display.container():
                            # Show recent logs
                            for log in logs[-30:]:
                                level = log['level']
                                msg = log['message']
                                
                                if level == 'ERROR':
                                    st.markdown(f"<span style='color: red;'>🔴 {msg}</span>", unsafe_allow_html=True)
                                elif level == 'WARNING':
                                    st.markdown(f"<span style='color: orange;'>🟡 {msg}</span>", unsafe_allow_html=True)
                                elif level == 'INFO':
                                    st.text(f"ℹ️  {msg}")
                                else:
                                    st.text(msg)
                        
                        last_log_count = len(logs)
                    
                    # Update status
                    dots = "." * ((iteration % 3) + 1)
                    status_msg.info(f"⏳ Operation in progress{dots} ({len(logs) if logs else 0} log entries)")
                    
                    iteration += 1
                    time.sleep(0.5)
                
                # Wait for completion
                op_thread.join(timeout=10)
                status_msg.empty()
                
                # Show final logs
                final_logs = StreamlitLogHandler.get_logs(max_lines=200)
                if final_logs:
                    with log_display.container():
                        for log in final_logs[-50:]:
                            level = log['level']
                            msg = log['message']
                            
                            if level == 'ERROR':
                                st.markdown(f"<span style='color: red;'>🔴 {msg}</span>", unsafe_allow_html=True)
                            elif level == 'WARNING':
                                st.markdown(f"<span style='color: orange;'>🟡 {msg}</span>", unsafe_allow_html=True)
                            elif level == 'INFO':
                                st.text(f"ℹ️  {msg}")
                            else:
                                st.text(msg)
                
                # Get result
                result = operation_result
                
                st.divider()
                
                if result.get('success'):
                    st.success(f"✅ {result.get('message')}")
                    
                    with st.expander("📋 Step-by-Step Results", expanded=False):
                        for step in result.get('steps', []):
                            step_name = step['step']
                            step_result = step['result']
                            if step_result.get('success'):
                                st.write(f"✅ {step_name}: {step_result.get('message', 'Success')}")
                            else:
                                st.write(f"❌ {step_name}: {step_result.get('error', 'Failed')}")
                else:
                    st.error(f"❌ {result.get('error', 'Failed to stop environment')}")
                    
                    if result.get('steps'):
                        with st.expander("📋 Step-by-Step Results", expanded=True):
                            for step in result.get('steps', []):
                                step_name = step['step']
                                step_result = step['result']
                                if step_result.get('success'):
                                    st.write(f"✅ {step_name}")
                                else:
                                    st.write(f"❌ {step_name}: {step_result.get('error')}")
            
            except Exception as e:
                st.error(f"❌ Operation failed with exception: {e}")
            
            finally:
                st.session_state.operation_running = False

            # Show detailed logs - AUTO EXPANDED and scrollable
            st.markdown("### 📜 Operation Logs")
            logs = StreamlitLogHandler.get_logs(max_lines=300)  # Get ALL logs, not just env-filtered
            if logs:
                # Create a scrollable container with all logs
                log_text = []
                for log in logs:
                    level = log['level']
                    msg = log['message']

                    # Format based on level
                    if level == 'ERROR':
                        log_text.append(f"🔴 {msg}")
                    elif level == 'WARNING':
                        log_text.append(f"🟡 {msg}")
                    else:
                        log_text.append(f"ℹ️  {msg}")

                # Display in a text area for better scrolling
                st.text_area(
                    "Logs",
                    value="\n".join(log_text),
                    height=400,
                    label_visibility="collapsed"
                )
            else:
                st.info("No logs captured for this operation")
    
    st.divider()
    
    # Bulk operations
    st.subheader("🎯 Bulk Operations")
    bulk_col1, bulk_col2 = st.columns(2)
    
    with bulk_col1:
        if st.button("▶️ Start All Environments", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, env in enumerate(environments):
                status_text.write(f"Starting {env}...")
                result = orch.start_environment(env)
                if result.get('success'):
                    st.success(f"✅ {env} started")
                else:
                    st.error(f"❌ {env} failed: {result.get('error')}")
                progress_bar.progress((idx + 1) / len(environments))
            
            status_text.write("All operations completed!")
    
    with bulk_col2:
        if st.button("⏹️ Stop All Environments", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, env in enumerate(environments):
                status_text.write(f"Stopping {env}...")
                result = orch.stop_environment(env)
                if result.get('success'):
                    st.success(f"✅ {env} stopped")
                else:
                    st.error(f"❌ {env} failed: {result.get('error')}")
                progress_bar.progress((idx + 1) / len(environments))
            
            status_text.write("All operations completed!")

# ===== TAB 2: Status =====
with tab2:
    st.header("📊 Environment Status")
    
    import time
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.session_state.last_refresh))}")
    with col2:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.session_state.last_refresh = time.time()
            st.rerun()
    
    # Show all environments
    for env in environments:
        with st.expander(f"🖥️ **{env.upper()}**", expanded=False):
            with st.spinner(f"Loading status for {env}..."):
                # Skip CloudSQL for faster loading (disable Compute API too)
                status = orch.get_simple_status(env, include_cloudsql=False)
            
            if status.get('success'):
                
                # Display key metrics
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                
                # Cluster State
                with metric_col1:
                    cluster_state = status.get('cluster_state', 'UNKNOWN')
                    state_color = "🟢" if cluster_state == "RUNNING" else "🔴"
                    st.metric("Cluster State", f"{state_color} {cluster_state}")
                
                # Node Count
                with metric_col2:
                    total_nodes = status.get('total_nodes', 0)
                    st.metric("Total Nodes", total_nodes)
                
                # CloudSQL Count
                with metric_col3:
                    cloudsql_list = status.get('cloudsql', [])
                    running_sql = sum(1 for db in cloudsql_list if 'RUNNABLE' in str(db.get('state', '')))
                    st.metric("CloudSQL Running", f"{running_sql}/{len(cloudsql_list)}")
                
                # Detailed info
                st.divider()
                
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.write("**Node Pools:**")
                    for np in status.get('node_pools', []):
                        st.write(f"• {np['name']}: {np['node_count']} nodes ({np['status']})")
                
                with detail_col2:
                    st.write("**CloudSQL Instances:**")
                    if cloudsql_list:
                        for db in cloudsql_list:
                            state_icon = "🟢" if 'RUNNABLE' in str(db.get('state')) else "🔴"
                            st.write(f"{state_icon} {db['name']}: {db['state']}")
                    else:
                        st.write("None configured")
            else:
                st.error(f"Failed to get status: {status.get('error')}")
    
    # Auto-refresh after 30 seconds
    if time.time() - st.session_state.last_refresh > 30:
        st.session_state.last_refresh = time.time()
        st.rerun()

# ===== TAB 3: Schedule =====
with tab3:
    st.header("⏰ Automated Schedule")
    
    st.info("""
    **Current Schedule (Asia/Kuala_Lumpur timezone):**
    
    🌙 **Stop Time**: 8:00 PM MYT (Monday - Friday)
    - Disable ArgoCD auto-sync
    - Suspend CronJobs
    - Delete PodDisruptionBudgets
    - Scale deployments to 0
    - Scale statefulsets to 0
    - Stop CloudSQL instances
    - Scale node pools to 0
    
    🌅 **Start Time**: 7:30 AM MYT (Monday - Friday)
    - Start CloudSQL instances
    - Scale node pools up
    - Enable ArgoCD auto-sync
    - Trigger ArgoCD sync
    - Resume CronJobs
    
    💰 **Cost Savings**: ~65-70 hours of downtime per week
    """)
    
    st.divider()
    
    st.subheader("📋 Managed Environments")
    for env in environments:
        st.write(f"✅ {env}")
    
    st.divider()
    
    st.subheader("ℹ️ System Information")
    st.write(f"**Total Environments**: {len(environments)}")
    st.write(f"**Schedule Status**: Active")
    st.write(f"**Timezone**: Asia/Kuala_Lumpur (MYT)")

# ===== TAB 4: Logs =====
with tab4:
    st.header("📜 System Logs")
    st.caption("💡 Real-time logs appear here during stop/start operations.")
    
    # Show operation status
    if st.session_state.operation_running:
        st.warning("⚠️ **OPERATION IN PROGRESS** - Do NOT refresh this page or it will kill the running operation!")
    
    # Disable auto-refresh when operation is running
    col_auto1, col_auto2 = st.columns([3, 1])
    with col_auto1:
        auto_refresh_enabled = not st.session_state.operation_running
        auto_refresh = st.checkbox(
            "🔄 Auto-refresh every 5 seconds", 
            value=False, 
            key="auto_refresh_logs",
            disabled=st.session_state.operation_running,
            help="Disabled during operations to prevent killing them"
        )
    with col_auto2:
        if auto_refresh and auto_refresh_enabled:
            import time
            time.sleep(5)
            st.rerun()

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        log_filter = st.selectbox(
            "Filter by level:",
            ["ALL", "INFO", "WARNING", "ERROR"],
            key="log_filter"
        )

    with col2:
        max_lines = st.slider(
            "Number of lines:",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            key="max_lines"
        )

    with col3:
        if st.button("🔄 Refresh", use_container_width=True, disabled=st.session_state.operation_running):
            st.rerun()

    st.divider()

    # Get logs
    if log_filter == "ALL":
        logs = StreamlitLogHandler.get_logs(max_lines=max_lines)
    else:
        logs = StreamlitLogHandler.get_logs(max_lines=max_lines, level_filter=log_filter)

    if logs:
        st.caption(f"Showing {len(logs)} most recent log entries")

        # Display logs in a container with scrolling
        log_container = st.container()
        with log_container:
            for log in logs:
                level = log['level']
                msg = log['message']

                # Color code by level
                if level == 'ERROR':
                    st.markdown(f"<span style='color: red;'>🔴 {msg}</span>", unsafe_allow_html=True)
                elif level == 'WARNING':
                    st.markdown(f"<span style='color: orange;'>🟡 {msg}</span>", unsafe_allow_html=True)
                elif level == 'INFO':
                    st.text(f"ℹ️  {msg}")
                else:
                    st.text(msg)
    else:
        st.info("No logs available. Logs will appear when operations are performed.")

    st.divider()

    # Clear logs button
    if st.button("🗑️ Clear All Logs", type="secondary"):
        StreamlitLogHandler.clear_logs()
        st.success("Logs cleared!")
        st.rerun()

    st.caption("💡 **Tip**: Logs are stored in memory and will be cleared when the container restarts.")

# Footer
st.divider()
st.caption("Dev Environment Manager v1.0 | Multi-Project GCP Environment Management")
