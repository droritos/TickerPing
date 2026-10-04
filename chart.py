import io
import logging
from typing import Optional
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

def generate_stock_chart(ticker: str, target_price: float, period: str = "5d") -> Optional[bytes]:
    """
    Generates a sleek dark-mode stock price chart with target line.
    Returns PNG image bytes in memory.
    """
    clean_ticker = ticker.strip().upper()
    try:
        t = yf.Ticker(clean_ticker)
        df = t.history(period=period, interval="15m" if period in ("1d", "5d") else "1d")
        
        if df.empty:
            df = t.history(period="1mo", interval="1d")
            
        if df.empty:
            logger.warning(f"No price history found for {clean_ticker}")
            return None

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(7, 3.5), dpi=140)
        
        # Color palette
        bg_outer = "#0b0f19"
        bg_inner = "#0f172a"
        line_color = "#22c55e" # emerald
        target_color = "#f59e0b" # amber
        
        fig.patch.set_facecolor(bg_outer)
        ax.set_facecolor(bg_inner)

        # Plot price line & gradient area
        ax.plot(df.index, df["Close"], color=line_color, linewidth=2, label=f"{clean_ticker} Price")
        ax.fill_between(df.index, df["Close"], df["Close"].min(), color=line_color, alpha=0.15)

        # Plot target price horizontal line
        if target_price > 0:
            ax.axhline(y=target_price, color=target_color, linestyle="--", linewidth=1.5, label=f"Target: ${target_price:,.2f}")

        # Polish aesthetics
        ax.set_title(f"{clean_ticker} Price Trend & Target", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)
        ax.tick_params(colors="#94a3b8", labelsize=8)
        ax.grid(color="#1e293b", linestyle=":", linewidth=0.5)
        ax.legend(loc="upper left", facecolor="#1e293b", edgecolor="#334155", fontsize=8)

        # Hide extra borders
        for spine in ax.spines.values():
            spine.set_color("#334155")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Error generating chart for {clean_ticker}: {e}")
        return None
