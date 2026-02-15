CREATE OR REPLACE VIEW demand_data.product_profitability AS
SELECT 
    p.sku, 
    p.product_name, 
    p.product_type, 
    AVG(sc.total_cost) as avg_total_cost, 
    AVG(sc.shipping_cost) as avg_shipping_cost, 
    p.price, 
    (p.price - AVG(sc.total_cost)) as avg_profit,
    (p.price - AVG(sc.total_cost)) / NULLIF(p.price, 0) as profit_margin, 
    p.stock_levels 
FROM demand_data.products p 
JOIN demand_data.supply_chain sc ON p.sku = sc.sku 
GROUP BY p.sku, p.product_name, p.product_type, p.price, p.stock_levels;
