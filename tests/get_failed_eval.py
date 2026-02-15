
import psycopg2
import json

def get_eval():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="unilever_poc",
            user="postgres",
            password="postgres"
        )
        cur = conn.cursor()
        
        query = """
            SELECT e.result, e.final_score, e.evaluation_data 
            FROM monitoring.evaluations e 
            JOIN monitoring.queries q ON e.query_id = q.query_id 
            WHERE q.query_text LIKE '%reordering%' 
            ORDER BY q.created_at DESC LIMIT 1;
        """
        
        cur.execute(query)
        row = cur.fetchone()
        
        if row:
            print(f"Result: {row[0]}")
            print(f"Final Score: {row[1]}")
            print(f"Evaluation Data: {json.dumps(row[2], indent=2)}")
        else:
            print("No matching query found.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    get_eval()
