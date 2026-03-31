import os
from pathlib import Path
import jaydebeapi

def load_dotenv(path: Path):
    if not path.exists(): return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

def main():
    load_dotenv(Path(".env"))
    jar = os.environ.get("ORACLE_JDBC_JAR", "jdbc/ojdbc8.jar")
    user = os.environ.get("ORACLE_USER")
    password = os.environ.get("ORACLE_PASSWORD")
    targets_raw = os.environ.get("ORACLE_TARGETS", "")
    
    targets = []
    for t in targets_raw.split(","):
        if t.strip():
            h, p, s = t.strip().split(":")
            targets.append((h, int(p), s))

    print(f"Intentando conectar como {user}...")
    
    conn = None
    for host, port, sid in targets:
        url = f"jdbc:oracle:thin:@{host}:{port}:{sid}"
        print(f"Probando {url}...")
        try:
            conn = jaydebeapi.connect("oracle.jdbc.OracleDriver", url, [user, password], jars=[jar])
            print(f"¡CONECTADO EXITOSAMENTE a {host}:{port}:{sid}!")
            curs = conn.cursor()
            curs.execute("SELECT 'Oracle responde correctamente' FROM DUAL")
            print("Prueba de consulta:", curs.fetchone()[0])
            break
        except Exception as e:
            print(f"Fallo en {host}: {e}")
    
    if conn:
        conn.close()
    else:
        print("NO SE PUDO CONECTAR A NINGÚN NODO.")

if __name__ == "__main__":
    main()
