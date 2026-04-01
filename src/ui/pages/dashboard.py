"""
Dashboard page showing family expense overview.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from storage.database import get_database
from services.dashboard_service import DashboardService


def show():
    """Display dashboard page."""
    st.title("Family Dashboard")
    st.caption("Analyze where your money goes by category across the current week, month, or year.")
    
    # Get dashboard data
    db = get_database()
    dashboard_service = DashboardService(db)
    
    try:
        period_label_map = {
            'week': 'This Week',
            'month': 'This Month',
            'year': 'This Year',
        }
        period = st.segmented_control(
            "Time Range",
            options=['week', 'month', 'year'],
            format_func=lambda value: period_label_map[value],
            default='month',
        )

        stats = dashboard_service.get_period_dashboard(st.session_state.family_id, period)
        trend_group_by = 'week' if period == 'year' else 'day'
        trend_days = 365 if period == 'year' else 31 if period == 'month' else 7
        trends = dashboard_service.get_spending_trends(
            st.session_state.family_id,
            days=trend_days,
            group_by=trend_group_by,
            start_date=stats['start_date'],
            end_date=stats['end_date'],
        )
        
        # Top metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(period_label_map[period], f"${stats['total_amount']:.2f}")
        with col2:
            st.metric("Receipts", int(stats['receipt_count']))
        with col3:
            st.metric("Tax Deductible", f"${stats['deductible_total']:.2f}")
        with col4:
            st.metric("Avg Per Receipt", f"${stats['average_amount']:.2f}")

        if stats['top_category']:
            st.info(
                f"Top category for {period_label_map[period].lower()}: "
                f"{stats['top_category']} (${stats['top_category_amount']:.2f})"
            )
        
        st.divider()
        
        # Charts row
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"Where The Money Went: {period_label_map[period]}")
            if stats['category_breakdown']:
                fig = px.pie(
                    values=list(stats['category_breakdown'].values()),
                    names=list(stats['category_breakdown'].keys()),
                    hole=0.3
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No expenses recorded yet")
        
        with col2:
            st.subheader("Spending by Category Ranking")
            if stats['category_rows']:
                fig = px.bar(
                    stats['category_rows'],
                    x='total',
                    y='category',
                    orientation='h',
                    text='total'
                )
                fig.update_layout(
                    xaxis_title='Amount ($)',
                    yaxis_title='Category',
                    yaxis={'categoryorder': 'total ascending'},
                )
                fig.update_traces(texttemplate='$%{text:.2f}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No category data available yet")

        st.divider()

        st.subheader("Spending Trend")
        if trends:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[t['period'] for t in trends],
                y=[t['total'] for t in trends],
                mode='lines+markers',
                name='Spending'
            ))
            fig.update_layout(
                xaxis_title='Period',
                yaxis_title='Amount ($)',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available yet")

        if stats['category_rows']:
            st.subheader("Category Breakdown Details")
            st.dataframe(stats['category_rows'], use_container_width=True, hide_index=True)
        
        st.divider()
        
        # Recent receipts
        st.subheader(f"Recent Receipts In {period_label_map[period]}")
        if stats['recent_receipts']:
            for receipt in stats['recent_receipts'][:5]:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    with col1:
                        st.write(f"**{receipt['merchant_name']}**")
                    with col2:
                        st.write(receipt['purchase_date'])
                    with col3:
                        st.write(f"${receipt['total_amount']:.2f}")
                    with col4:
                        st.write(receipt['category'])
        else:
            st.info("No receipts yet. Upload your first receipt to get started!")
        
        # Tax deduction summary
        st.divider()
        st.subheader("Tax Deductible Expenses")
        
        deduction_summary = dashboard_service.get_deduction_summary(
            st.session_state.family_id,
            start_date=stats['start_date'],
            end_date=stats['end_date'],
        )
        
        if deduction_summary['summary_by_type']:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.metric("Total Deductible", f"${deduction_summary['total_deductible']:.2f}")
                st.metric("Deductible Items", deduction_summary['total_items'])
            
            with col2:
                for dtype, data in deduction_summary['summary_by_type'].items():
                    st.write(f"**{dtype.title()}**: ${data['total_amount']:.2f} ({data['count']} items)")
        else:
            st.info("No tax deductible expenses found for this period")
            
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
