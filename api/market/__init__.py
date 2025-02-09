"""Market data endpoints for statistics and trends."""

from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from decimal import Decimal
from database import get_pool

# Create router
router = APIRouter(
    prefix="/market",
    tags=["Market"]
)

class MarketStats(BaseModel):
    """Model for market statistics."""
    total_listings: int
    active_listings: int
    total_sales: int
    total_volume: Decimal
    unique_sellers: int
    unique_buyers: int
    avg_sale_price: Decimal
    popular_payment_methods: Dict[str, int]
    sales_by_day: Dict[str, int]

class TrendingItem(BaseModel):
    """Model for trending items."""
    listing_id: str
    title: str
    price_evr: Decimal
    views_24h: int
    sales_24h: int
    trend_score: float

@router.get("/stats")
async def get_market_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> MarketStats:
    """Get market-wide statistics.
    
    Args:
        start_date: Optional start date for stats period
        end_date: Optional end date for stats period
        
    Returns:
        MarketStats object containing market metrics
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Use default date range if not specified
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Get listing counts
            listing_counts = await conn.fetchrow(
                '''
                SELECT 
                    COUNT(*) as total_listings,
                    COUNT(*) FILTER (WHERE status = 'active') as active_listings
                FROM listings
                '''
            )
            
            # Get sales metrics
            sales_metrics = await conn.fetchrow(
                '''
                SELECT 
                    COUNT(*) as total_sales,
                    COALESCE(SUM(price_evr), 0) as total_volume,
                    COUNT(DISTINCT seller_address) as unique_sellers,
                    COUNT(DISTINCT buyer_address) as unique_buyers,
                    COALESCE(AVG(price_evr), 0) as avg_sale_price
                FROM sale_history
                WHERE sale_time BETWEEN $1 AND $2
                ''',
                start_date,
                end_date
            )
            
            # Get payment method distribution
            payment_methods = await conn.fetch(
                '''
                SELECT asset_name, COUNT(*) as count
                FROM sale_history
                WHERE sale_time BETWEEN $1 AND $2
                GROUP BY asset_name
                ORDER BY count DESC
                ''',
                start_date,
                end_date
            )
            
            # Get daily sales
            daily_sales = await conn.fetch(
                '''
                SELECT 
                    DATE_TRUNC('day', sale_time) as sale_date,
                    COUNT(*) as count
                FROM sale_history
                WHERE sale_time BETWEEN $1 AND $2
                GROUP BY DATE_TRUNC('day', sale_time)
                ORDER BY sale_date
                ''',
                start_date,
                end_date
            )
            
            return MarketStats(
                total_listings=listing_counts['total_listings'],
                active_listings=listing_counts['active_listings'],
                total_sales=sales_metrics['total_sales'],
                total_volume=sales_metrics['total_volume'],
                unique_sellers=sales_metrics['unique_sellers'],
                unique_buyers=sales_metrics['unique_buyers'],
                avg_sale_price=sales_metrics['avg_sale_price'],
                popular_payment_methods={
                    pm['asset_name']: pm['count']
                    for pm in payment_methods
                },
                sales_by_day={
                    ds['sale_date'].strftime("%Y-%m-%d"): ds['count']
                    for ds in daily_sales
                }
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/trending")
async def get_trending_items(
    category: Optional[str] = None,
    time_frame: str = Query("24h", regex="^(24h|7d|30d)$")
) -> List[TrendingItem]:
    """Get currently trending items based on views and sales.
    
    Args:
        category: Optional category to filter by
        time_frame: Time frame for trend calculation (24h/7d/30d)
        
    Returns:
        List of TrendingItem objects
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Calculate time frame
            end_date = datetime.utcnow()
            if time_frame == "24h":
                start_date = end_date - timedelta(hours=24)
            elif time_frame == "7d":
                start_date = end_date - timedelta(days=7)
            else:  # 30d
                start_date = end_date - timedelta(days=30)
            
            # Build query
            query = '''
                WITH metrics AS (
                    SELECT 
                        l.id as listing_id,
                        l.title,
                        l.price_evr,
                        COUNT(DISTINCT v.id) as views,
                        COUNT(DISTINCT s.id) as sales,
                        (COUNT(DISTINCT v.id) * 0.3 + COUNT(DISTINCT s.id) * 0.7) as trend_score
                    FROM listings l
                    LEFT JOIN listing_views v ON v.listing_id = l.id 
                        AND v.view_time BETWEEN $1 AND $2
                    LEFT JOIN sale_history s ON s.listing_id = l.id 
                        AND s.sale_time BETWEEN $1 AND $2
                    WHERE l.status = 'active'
            '''
            params = [start_date, end_date]
            
            if category:
                query += " AND l.category = $3"
                params.append(category)
                
            query += '''
                    GROUP BY l.id, l.title, l.price_evr
                )
                SELECT *
                FROM metrics
                WHERE trend_score > 0
                ORDER BY trend_score DESC
                LIMIT 20
            '''
            
            trending = await conn.fetch(query, *params)
            
            return [
                TrendingItem(
                    listing_id=item['listing_id'],
                    title=item['title'],
                    price_evr=item['price_evr'],
                    views_24h=item['views'],
                    sales_24h=item['sales'],
                    trend_score=float(item['trend_score'])
                )
                for item in trending
            ]
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export the router
__all__ = ['router'] 