import streamlit as st

from market_relationship_discovery import __version__
from market_relationship_discovery.config import get_settings
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.relationships.catalog import RelationshipCatalog

st.set_page_config(page_title="Market Relationship Discovery", layout="wide")
st.warning("DEMO / RESEARCH MODE — NO LIVE TRADING")
settings = get_settings()
st.title("Market Relationship Discovery")
st.caption(f"Version {__version__} — research candidates are not guaranteed opportunities")

overview, monitor, relationships, limitations = st.tabs(
    ["Overview", "Market Monitor", "Relationship Explorer", "Limitations"]
)

with overview:
    st.write(f"Configured terminal: `{settings.mt5.terminal_path or 'not configured'}`")
    st.write(f"Demo-only safety: **{settings.mt5.demo_only}**")
    st.write("No order execution methods are implemented.")

with monitor:
    if st.button("Connect to configured MT5 terminal"):
        try:
            with MT5Adapter(settings.mt5) as adapter:
                account = adapter.account_info()
                st.success(f"Connected to {account.server} ({account.mode})")
                rows = [
                    {
                        "Symbol": symbol,
                        "Bid": adapter.current_quote(symbol).bid,
                        "Ask": adapter.current_quote(symbol).ask,
                        "Timestamp (UTC)": adapter.current_quote(symbol).timestamp,
                    }
                    for symbol in list(settings.symbol_mapping)[:8]
                ]
                st.dataframe(rows, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))

with relationships:
    catalog = RelationshipCatalog()
    st.dataframe(
        [
            {
                "Name": item.name,
                "Target": item.target,
                "Formula": item.formula,
                "Status": item.classification,
            }
            for item in catalog.all()
        ],
        use_container_width=True,
    )

with limitations:
    st.markdown("""
Correlation is not arbitrage. A mid-price discrepancy can vanish after spread,
commission, slippage, latency, session differences, feed differences, and symbol
construction. Historical mean reversion does not guarantee future behavior.
""")
