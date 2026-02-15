
import pandas as pd
import psycopg2
from loguru import logger
from config.settings import settings
from database.schemas import create_data_schemas


def load_superstore_data():
    
    try:
        logger.info("Loading SuperStoreOrders.csv...")

        
        df = pd.read_csv('data/SuperStoreOrders.csv', encoding='latin1')
        
        df.columns = [col.replace('ï»¿', '') for col in df.columns]
        logger.info(f"Loaded {len(df)} rows from SuperStoreOrders.csv")

        
        numeric_cols = ['sales', 'quantity', 'discount', 'profit', 'shipping_cost']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').astype(float)

        
        df['order_date'] = pd.to_datetime(df['order_date'], format='mixed', dayfirst=False)
        df['ship_date'] = pd.to_datetime(df['ship_date'], format='mixed', dayfirst=False)

        
        if 'year' not in df.columns:
            df['year'] = df['order_date'].dt.year

        
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        
        logger.info("Inserting customers...")
        customers = df[['customer_name', 'segment', 'state', 'country', 'market', 'region']].drop_duplicates()

        customer_map = {}
        for idx, row in customers.iterrows():
            cursor.execute("""
                INSERT INTO spend_data.customers (customer_name, segment, state, country, market, region)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (customer_name) DO UPDATE SET customer_name = EXCLUDED.customer_name
                RETURNING customer_id
            """, (row['customer_name'], row['segment'], row['state'], row['country'], row['market'], row['region']))
            customer_id = cursor.fetchone()[0]
            customer_map[row['customer_name']] = customer_id

        logger.info(f"Inserted {len(customer_map)} unique customers")

        
        logger.info("Inserting products...")
        products = df[['product_id', 'product_name', 'category', 'sub_category']].drop_duplicates()

        for idx, row in products.iterrows():
            cursor.execute("""
                INSERT INTO spend_data.products (product_id, product_name, category, sub_category)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (product_id) DO NOTHING
            """, (row['product_id'], row['product_name'], row['category'], row['sub_category']))

        logger.info(f"Inserted {len(products)} unique products")

        
        logger.info("Inserting orders...")
        order_count = 0
        for idx, row in df.iterrows():
            customer_id = customer_map[row['customer_name']]

            cursor.execute("""
                INSERT INTO spend_data.orders (
                    order_id, order_date, ship_date, ship_mode, customer_id, product_id,
                    sales, quantity, discount, profit, shipping_cost, order_priority, year
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id) DO NOTHING
            """, (
                row['order_id'], row['order_date'], row['ship_date'], row['ship_mode'],
                customer_id, row['product_id'], row['sales'], row['quantity'],
                row['discount'], row['profit'], row['shipping_cost'],
                row['order_priority'], row['year']
            ))
            order_count += 1

            if order_count % 5000 == 0:
                conn.commit()
                logger.info(f"Inserted {order_count} orders...")

        conn.commit()
        logger.info(f"✅ Successfully loaded {order_count} orders from SuperStoreOrders.csv")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error loading SuperStore data: {e}")
        return False


def load_supply_chain_data():
    
    try:
        logger.info("Loading supply_chain_data.csv...")

        
        df = pd.read_csv('data/supply_chain_data.csv')
        logger.info(f"Loaded {len(df)} rows from supply_chain_data.csv")

        
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        
        logger.info("Inserting products...")
        for idx, row in df.iterrows():
            cursor.execute("""
                INSERT INTO demand_data.products (sku, product_type, price, availability, stock_levels, customer_demographics)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sku) DO NOTHING
            """, (
                row['SKU'], row['Product type'], row['Price'],
                row['Availability'], row['Stock levels'], row['Customer demographics']
            ))

        logger.info(f"Inserted {len(df)} products")

        
        logger.info("Inserting suppliers...")
        suppliers = df[['Supplier name', 'Location', 'Lead time', 'Shipping carriers', 'Transportation modes', 'Routes']].drop_duplicates()
        supplier_map = {}

        for idx, row in suppliers.iterrows():
            cursor.execute("""
                INSERT INTO demand_data.suppliers (supplier_name, location, lead_time, shipping_carrier, transportation_mode, route)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (supplier_name) DO UPDATE SET supplier_name = EXCLUDED.supplier_name
                RETURNING supplier_id
            """, (
                row['Supplier name'], row['Location'], row['Lead time'],
                row['Shipping carriers'], row['Transportation modes'], row['Routes']
            ))
            supplier_id = cursor.fetchone()[0]
            supplier_map[row['Supplier name']] = supplier_id

        logger.info(f"Inserted {len(supplier_map)} unique suppliers")

        
        logger.info("Inserting sales...")
        for idx, row in df.iterrows():
            cursor.execute("""
                INSERT INTO demand_data.sales (sku, products_sold, revenue_generated, order_quantities)
                VALUES (%s, %s, %s, %s)
            """, (
                row['SKU'], row['Number of products sold'],
                row['Revenue generated'], row['Order quantities']
            ))

        logger.info(f"Inserted {len(df)} sales records")

        
        logger.info("Inserting supply chain data...")
        for idx, row in df.iterrows():
            supplier_id = supplier_map[row['Supplier name']]

            cursor.execute("""
                INSERT INTO demand_data.supply_chain (
                    sku, supplier_id, lead_time, shipping_time, shipping_cost,
                    production_volume, manufacturing_lead_time, manufacturing_cost,
                    inspection_result, defect_rate, total_cost
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['SKU'], supplier_id, row['Lead times'], row['Shipping times'],
                row['Shipping costs'], row['Production volumes'],
                row['Manufacturing lead time'], row['Manufacturing costs'],
                row['Inspection results'], row['Defect rates'], row['Costs']
            ))

        conn.commit()
        logger.info(f"✅ Successfully loaded {len(df)} records from supply_chain_data.csv")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error loading supply chain data: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    
    logger.info("Starting data loading process...")

    
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        
        logger.info("Creating data table schemas...")
        if create_data_schemas(cursor):
            conn.commit()
            logger.info("✅ Data schemas created successfully")
        else:
            logger.error("❌ Failed to create data schemas")
            return False

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error creating schemas: {e}")
        return False

    
    if not load_superstore_data():
        logger.error("❌ Failed to load SuperStore data")
        return False

    
    if not load_supply_chain_data():
        logger.error("❌ Failed to load supply chain data")
        return False

    logger.info("✅ All data loaded successfully!")
    return True


if __name__ == "__main__":
    logger.add("logs/data_loading.log", rotation="10 MB")
    success = main()

    if success:
        print("\n✅ Data loading completed successfully!")
        print("\nDatabase summary:")
        print("- Spend Agent: SuperStoreOrders loaded")
        print("- Demand Agent: supply_chain_data loaded")
    else:
        print("\n❌ Data loading failed. Check logs for details.")
