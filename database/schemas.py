
SPEND_SCHEMA_SQL = """
-- Customers table (dimension)
CREATE TABLE IF NOT EXISTS spend_data.customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(200) UNIQUE NOT NULL,
    segment VARCHAR(50),
    state VARCHAR(100),
    country VARCHAR(100),
    market VARCHAR(50),
    region VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table (dimension)
CREATE TABLE IF NOT EXISTS spend_data.products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(300) NOT NULL,
    category VARCHAR(50),
    sub_category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders table (fact table)
CREATE TABLE IF NOT EXISTS spend_data.orders (
    order_id VARCHAR(50) PRIMARY KEY,
    order_date DATE NOT NULL,
    ship_date DATE,
    ship_mode VARCHAR(50),
    customer_id INTEGER REFERENCES spend_data.customers(customer_id),
    product_id VARCHAR(50) REFERENCES spend_data.products(product_id),
    sales DECIMAL(12,2),
    quantity INTEGER,
    discount DECIMAL(5,2),
    profit DECIMAL(12,2),
    shipping_cost DECIMAL(12,2),
    order_priority VARCHAR(20),
    year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_orders_date ON spend_data.orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON spend_data.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_product ON spend_data.orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_year ON spend_data.orders(year);
CREATE INDEX IF NOT EXISTS idx_customers_name ON spend_data.customers(customer_name);
CREATE INDEX IF NOT EXISTS idx_products_category ON spend_data.products(category);
"""


DEMAND_SCHEMA_SQL = """
-- Products table
CREATE TABLE IF NOT EXISTS demand_data.products (
    sku VARCHAR(50) PRIMARY KEY,
    product_type VARCHAR(100),
    price DECIMAL(10,2),
    availability INTEGER,
    stock_levels INTEGER,
    customer_demographics VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suppliers table
CREATE TABLE IF NOT EXISTS demand_data.suppliers (
    supplier_id SERIAL PRIMARY KEY,
    supplier_name VARCHAR(200) UNIQUE NOT NULL,
    location VARCHAR(200),
    lead_time INTEGER,
    shipping_carrier VARCHAR(100),
    transportation_mode VARCHAR(50),
    route VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sales table
CREATE TABLE IF NOT EXISTS demand_data.sales (
    sales_id SERIAL PRIMARY KEY,
    sku VARCHAR(50) REFERENCES demand_data.products(sku),
    products_sold INTEGER,
    revenue_generated DECIMAL(12,2),
    order_quantities INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Supply Chain table
CREATE TABLE IF NOT EXISTS demand_data.supply_chain (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) REFERENCES demand_data.products(sku),
    supplier_id INTEGER REFERENCES demand_data.suppliers(supplier_id),
    lead_time INTEGER,
    shipping_time INTEGER,
    shipping_cost DECIMAL(10,2),
    production_volume INTEGER,
    manufacturing_lead_time INTEGER,
    manufacturing_cost DECIMAL(10,2),
    inspection_result VARCHAR(50),
    defect_rate DECIMAL(5,2),
    total_cost DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_type ON demand_data.products(product_type);
CREATE INDEX IF NOT EXISTS idx_products_stock ON demand_data.products(stock_levels);
CREATE INDEX IF NOT EXISTS idx_sales_sku ON demand_data.sales(sku);
CREATE INDEX IF NOT EXISTS idx_supply_chain_sku ON demand_data.supply_chain(sku);
CREATE INDEX IF NOT EXISTS idx_supply_chain_supplier ON demand_data.supply_chain(supplier_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON demand_data.suppliers(supplier_name);
"""

def create_data_schemas(cursor):
    
    try:
        
        cursor.execute(SPEND_SCHEMA_SQL)
        print("✅ Spend Agent schema created successfully")

        
        cursor.execute(DEMAND_SCHEMA_SQL)
        print("✅ Demand Agent schema created successfully")

        return True
    except Exception as e:
        print(f"❌ Error creating data schemas: {e}")
        return False
