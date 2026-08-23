# Azure Free Tier pro MCP-Jobs — Edukacni dokument

**Autor:** Ondrej Sousek (SYSTEQ) | **Datum:** 2026-08-23 | **Verze:** 1.0
**Ucel:** Vstupni dokument s edukacnim charakterem do ekosystemu Azure
**Metoda:** Feynman (destilace do jednoduchych prikladu)
**Navezost:** SKILL_GAPS_ROZBOR_Q3_2026_v2 (gap 4: AZ-900), DEPLOY.md, sync_to_cloud.py

---

## CAST 1: Proc Azure? (a proc nejen Supabase/Neon)

### 1.1 Tri moznosti cloud PostgreSQL

| Sluzba | Free tier | Trvani | Co dostanes | Co chybi |
|--------|-----------|--------|-------------|---------|
| **Supabase** | 500 MB, 50k reads/den | Neomezeno (do limitu) | PostgREST, auth, real-time, dashboard | Storage limit, shared CPU |
| **Neon** | 512 MB, 100h compute/mesic | Neomezeno (do limitu) | Branching, serverless scale | Compute limit, zadna VM |
| **Azure PostgreSQL** | 32 GB, B1ms, 750h/mesic | **12 mesicu** | Managed PostgreSQL, HA, backup, monitoring | Po 12 mesicich plati |

### 1.2 Proc Azure misto Supabase/Neon?

**Feynman analogie:**
- Supabase/Neon = pronajem garsonky (levne, jednoduche, ale nespravis tam rekonstrukci)
- Azure = pronajem bytu s nastroji (muzes si ho prizpusobit, naucis se jak byt funguje)

**Klicove rozdily:**

| Co | Supabase/Neon | Azure |
|----|---------------|-------|
| PostgreSQL | Shared CPU, omezeny pristup | Dedicated B1ms, plny pristup |
| Konfigurace | Zadna (managed) | `az postgres flexible-server configure` |
| Firewall | Pres dashboard | IP-based firewall rules (produkcni koncept) |
| Backup | Automaticky (omezeny retention) | Az 35 dni, geo-redundant |
| Monitoring | Zadny | Azure Monitor, metrics, alerts |
| **Uceni** | "Pouzivam" | **"Rozumim jak to funguje"** |

### 1.3 Autoruv kontext — proc prave ted?

```
SKILL_GAPS gap 4: AZ-900 Azure Fundamentals (7.5/10 EROI)
  ↓
Azure free tier = $0 imerze na 12 mesicu
  ↓
MCP-Jobs deploy = realny projekt = PBL metoda (60% podilu)
  ↓
AZ-900 certifikace = logicky nasledek (10-15h)
```

**EROI kalkulace:**
- Cas na Azure deploy: ~5-8 hodin
- Ziskane dovednosti: PostgreSQL v cloudu, firewall rules, VM sprava, Docker deploy, SSL
- AZ-900 priprava: ~10-15 hodin (ale uz budes znat zaklady z praxe)
- **Celkem: ~20-25 hodin = 2 gapy (DB + DevOps) + polovina AZ-900**

---

## CAST 2: Zakladni ontologie Azure

### 2.1 Co je Azure?

**Feynman:** Azure je jako velky sklad s nastroji. Pronajimas si cast skladu (VM, DB, storage) a platis jen za to co pouzivas. Nejsi spravce budovy — jen si pronajimas misto a nastroje.

### 2.2 Zakladni pojmy

| Pojem | Feynman vysvetleni | Priklad |
|-------|-------------------|---------|
| **Subscription** | Tvoje kreditni karta u Azure. Vsechno co vytvoris, jde na tento ucet. | "Muj Azure ucet" |
| **Resource Group** | Slozka v Exploreru. Vseschno co patri k projektu das do jedne slozky. | `rg-mcpjobs-prod` |
| **Region** | Kde fyzicky běží tvoje věci. Praha = `westeurope`, US = `eastus`. | `westeurope` (blizko CR) |
| **Resource** | Cokoliv co vytvoris — server, databaze, disk, IP adresa. | PostgreSQL server, B1S VM |
| **SKU** | Typ a velikost. jako vyber auta — maly/velky, slabý/výkonný. | B1ms (1 vCore, 2 GB RAM) |
| **Tier** | Cena/kvalita tier. Bursted = intermittently, General Purpose = stabilized. | Burstable (dev), General Purpose (prod) |

### 2.3 Azure sluzby pro MCP-Jobs

```
MCP-Jobs cloud deploy
├── PostgreSQL Database (managed)
│   └── Azure Database for PostgreSQL Flexible Server
│       └── B1ms Burstable = 1 vCore, 2 GB RAM, 32 GB storage
│           └── Free: 750 hodin/mesic, 12 mesicu
│
├── Virtual Machine (pro Streamlit dashboard)
│   └── Azure Virtual Machine B1S
│       └── 1 vCPU, 1 GB RAM, Ubuntu Linux
│           └── Free: 750 hodin/mesic, 12 mesicu
│
├── Networking
│   ├── Public IP adresa (pro pristup k VM)
│   ├── NSG (Network Security Group) = firewall pravidla
│   └── DNS (jmeno jako `jobs.systeq.cz`)
│
├── Storage
│   ├── Managed Disk (pro VM disk)
│   └── Blob Storage (pro backupy)
│
└── Identity & Access
    ├── Microsoft Entra ID (Azure AD)
    └── RBAC (kdo muze delat co)
```

### 2.4 Azure Portal — zakladni navigace

**Feynman:** Portal je jako ovladaci panel auta. Vlevo mas菜单 (Engine, Brakes, Lights), uprostřed dashboard, vpravo nastavení.

```
portal.azure.com
├── Home              # Prehled, posledni resources
├── All services      # Seznam vsech dostupnych sluzeb
├── Resource groups   # Tvoje slozky (rg-mcpjobs-prod)
├── Subscriptions     # Kreditni karta (billing, limity)
├── Cost Management   # Kolik utracis, alerts
└── Search            # Hledej cokoliv (PostgreSQL, VM, ...)
```

---

## CAST 3: Azure vs Supabase/Neon — srovnani

### 3.1 Pro koho je co?

| Typ uzivatele | Doporuceni | Duvod |
|---------------|-----------|-------|
| Chci jen nasadit dashboard | **Supabase** | Nejrychlejsi cesta, 0 konfigurace |
| Chci se naucit Azure | **Azure** | Hands-on imerze, zaklady pro AZ-900 |
| Chci produkci na roky | **Azure** | Dedikovane zdroje, SLA, monitoring |
| Mam cas 5 minut | **Supabase** | 1 klik, hotovo |
| Mam cas 5 hodin | **Azure** | Cela architektura, velky learning |

### 3.2 Funkcni srovnani

| Feature | Supabase | Neon | Azure PostgreSQL |
|---------|----------|------|-----------------|
| PostgreSQL verze | 15 | 16 | 16/17/18 |
| Dedicated CPU | Ne (shared) | Ne (serverless) | **Ano** (B1ms) |
| Connection pooling | Ano (PgBouncer) | Ano | **Ano** (built-in PgBouncer) |
| Branching | Ne | **Ano** (DB branching) | Ne |
| Firewall rules | Pres dashboard | Pres dashboard | **Azure NSG + IP rules** |
| Backup retention | 7 dni | 7 dni | **Az 35 dni** |
| Monitoring | Zadny | Zadny | **Azure Monitor + alerts** |
| Custom domain | Ne (pro DB) | Ne (pro DB) | Ano (FQDN) |
| SSL/TLS | Povinny | Povinny | **Povinny + konfigurovatelny** |
| Free tier trvani | Neomezeno | Neomezeno | **12 mesicu** |

### 3.3 Kdyz selze free tier

| Scenar | Supabase/Neon | Azure |
|--------|---------------|-------|
| Presahnu limit | App pada nebo se omezi | Platis pay-as-you-go |
| Po 12 mesicich | Porad zdarma (do limitu) | **Prepnes na placeny nebo zrusis** |
| Optimalizace | Minimalni (managed) | Muzes menit SKU, storage, backupy |

---

## CAST 4: Krok po kroku — migrace na Azure

### 4.0 Predpoklady

```
- Lokalni PostgreSQL bezi (Docker: mcpjobs-postgres)
- Data: 187 ads, 30 pipeline_runs
- MCP-Jobs repo: outpost2026/MCP-Jobs
- Windows PC s PowerShell
```

### FAZE 1: Vytvoreni Azure uctu (15 minut)

```
1. Otevri https://azure.microsoft.com/free
2. Klikni "Start for free"
3. Prihlas se pres Microsoft ucet (nebo vytvor novy)
4. Over kreditni kartou ($1 docasne blokovani, vrati se)
5. Hotovo — mas $200 kredit na 30 dni + 12 mesicu free tier
```

**Co se deje v pozadi:**
- Azure vytvari subscription (tvoje "kreditni karta")
- Dostavas $200 kredit na 30 dni na cokoliv
- Po 30 dnech: automaticky prepnuti na pay-as-you-go
- Free tier sluzby (PostgreSQL, VM) zustavaji zdarma na 12 mesicu

### FAZE 2: Vytvoreni PostgreSQL serveru (20 minut)

**V Azure Portal:**

```
1. portal.azure.com → "Create a resource"
2. Hledej "Azure Database for PostgreSQL" → Flexible Server
3. Nastaveni:
   ├── Subscription: "Free Trial" (nebo "Pay-as-you-go")
   ├── Resource group: "rg-mcpjobs-prod" (vytvorit novou)
   ├── Server name: "mcpjobs-pgsql" (musi byt unikatni globalne)
   ├── Region: "West Europe" (blizko CR)
   ├── PostgreSQL version: 16
   ├── Workload type: "Development" (Burstable)
   ├── Compute tier: "Burstable"
   ├── SKU name: "Standard_B1ms" (1 vCore, 2 GB RAM)
   └── Storage: 32 GB (maximum pro free tier)

4. Authentication:
   ├── Authentication method: "PostgreSQL authentication only"
   ├── Admin username: "mcpjobsadmin"
   └── Password: [silne heslo — minimum 8 znaku, cisla+pismena+symboly]

5. Networking:
   ├── Connectivity method: "Public access (allowed IP addresses)"
   ├── Allow public access: ✅
   ├── Allow Azure services: ✅ (pro pozdejsi VM deploy)
   └── Add current client IP: ✅ (tvuj PC IP)

6. Review + Create → Create
```

**Cas vytvoreni:** ~5-10 minut

### FAZE 3: Pripojeni z PowerShellu (5 minut)

```powershell
# Ziskej connection string z Azure Portal
# Overview → Connection strings → JDBC/PSQL/ADO.NET
# Kopiruj "postgresql" format

# Pripoj se pres psql
psql "host=mcpjobs-pgsql.postgres.database.azure.com port=5432 dbname=postgres user=mcpjobsadmin sslmode=require"

# Po pripojeni vytvor databazi
CREATE DATABASE mcpjobs;
\c mcpjobs
\q
```

**Feynman:** SSL = zamceny obalka. Bez ni Azure rekne "ne, nepustim te". `sslmode=require` = "posilam zamcenou obalku".

### FAZE 4: Inicializace schema (5 minut)

```powershell
# Nacti schema do cloud DB
$CLOUD_URL = "postgresql://mcpjobsadmin:VASE_HESLO@mcpjobs-pgsql.postgres.database.azure.com:5432/mcpjobs?sslmode=require"

# Pomoc psql
psql $CLOUD_URL -f data/schema.sql
```

**Overeni:**
```sql
-- V Azure Portal: Query editor (nebo psql)
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
-- Melo by ukazat: ads, pipeline_runs
```

### FAZE 5: Sync dat z lokální DB do Azure (10 minut)

```powershell
# Ujisti se ze lokalni DB bezi
docker ps | Select-String mcpjobs

# Spust sync
$env:DATABASE_URL = "postgresql://mcpjobs:mcpjobs@localhost:5432/mcpjobs"
python scripts/sync_to_cloud.py --cloud-url $CLOUD_URL

# Vystup:
#   Ads: 187, Pipeline runs: 30
#   Ads upserted: 187 (2 batches)
#   Pipeline runs upserted: 30
```

### FAZE 6: Overeni dat v Azure (5 minut)

```powershell
# Pripoj se a over
psql $CLOUD_URL

# Kontrola
SELECT count(*) FROM ads;        -- melo by byt 187
SELECT count(*) FROM pipeline_runs; -- melo by byt 30
SELECT portal, count(*) FROM ads GROUP BY portal; -- rozlozeni dle portalu
```

### FAZE 7: Deploy Streamlit na Azure VM (30-45 minut)

#### 7.1 Vytvoreni VM

```
1. portal.azure.com → "Create a resource" → "Virtual machine"
2. Nastaveni:
   ├── Subscription: "Free Trial"
   ├── Resource group: "rg-mcpjobs-prod" (stejna jako DB)
   ├── Virtual machine name: "vm-mcpjobs-dashboard"
   ├── Region: "West Europe"
   ├── Image: "Ubuntu 24.04 LTS"
   ├── Size: "Standard_B1s" (1 vCPU, 1 GB RAM) — FREE
   ├── Authentication: SSH public key
   │   └── Vyber nebo nahraj svuj SSH klic
   ├── Port rules:
   │   ├── SSH (22): ✅
   │   ├── HTTP (80): ✅
   │   └── HTTPS (443): ✅
   └── Disk: 30 GB (standard SSD)

3. Review + Create → Create
```

#### 7.2 Pripojeni pres SSH

```powershell
# Ziskej public IP z Azure Portal
$VM_IP = "XX.XX.XX.XX"  # tvuj VM IP

# Pripoj se
ssh azureuser@$VM_IP

# Pokud mas heslo misto SSH klice:
ssh azureuser@$VM_IP -o PreferredAuthentications=password
```

#### 7.3 Instalace Docker + Streamlit

```bash
# Na Azure VM (Ubuntu):

# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Nainstaluj Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 3. Odhlas se a prihlas znovu (aby fungoval docker group)
exit
ssh azureuser@$VM_IP

# 4. Over Docker
docker --version
```

#### 7.4 Vytvoreni Dockerfile

```bash
# Vytvor adresar
mkdir -p /opt/mcpjobs
cd /opt/mcpjobs

# Vytvor Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.12-slim

WORKDIR /app

# Systemove zavislosti
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Python zavislosti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopirovani kodu
COPY src/ src/
COPY dashboard/ dashboard/
COPY data/schema.sql data/schema.sql

# Vystupni port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Spusteni Streamlit
ENTRYPOINT ["streamlit", "run", "dashboard/app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
EOF
```

#### 7.5 Vytvoreni docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
services:
  dashboard:
    build: .
    container_name: mcpjobs-dashboard
    restart: unless-stopped
    ports:
      - "8501:8501"
    environment:
      - DATABASE_URL=postgresql://mcpjobsadmin:VASE_HESLO@mcpjobs-pgsql.postgres.database.azure.com:5432/mcpjobs?sslmode=require
      - MCPJOBS_DASH_PWD=VADE_DEMO_HESLO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF
```

#### 7.6 Vytvoreni requirements.txt

```bash
cat > requirements.txt << 'EOF'
streamlit>=1.38.0
pandas>=2.0
psycopg[binary]>=3.1
EOF
```

#### 7.7 Deploy

```bash
cd /opt/mcpjobs

# Sestav a spust
docker compose up -d --build

# Over
docker compose ps
docker compose logs dashboard

# Otestuj pristup
curl http://localhost:8501/_stcore/health
```

### FAZE 8: Konfigurace firewallu (10 minut)

#### 8.1 NSG (Network Security Group)

```
1. Azure Portal → VM → Networking
2. Inbound security rules:
   ├── AllowSSH (22)     ✅  (z tvé IP only)
   ├── AllowHTTP (80)    ✅  (pro Let's Encrypt challenge)
   ├── AllowHTTPS (443)  ✅  (pro HTTPS)
   └── AllowStreamlit (8501) ✅  (docasne, pro testovani)

3. Upozorneni: Port 8501 je docasny. Pozdeji budes pres nginx na port 80/443.
```

#### 8.2 Azure PostgreSQL firewall

```
1. Azure Portal → PostgreSQL → Networking
2. Firewall rules:
   ├── AllowMyPC: [tva-verejna-IP] — pro lokalni sync
   ├── AllowAzureServices: 0.0.0.0 — pro VM pristup
   └── Pozor: meni se az za 5 minut!
```

### FAZE 9: Overeni celyho stacku (10 minut)

```powershell
# 1. Over ze VM bezi
ssh azureuser@$VM_IP "docker compose -f /opt/mcpjobs/docker-compose.yml ps"

# 2. Over ze dashboard odpovida
curl http://$VM_IP:8501/_stcore/health

# 3. Otevri v prohlizeci
Start-Process "http://$VM_IP:8501"

# 4. Over ze data nacitava z Azure DB
# (v dashboardu by mely byt 187 ads)
```

### FAZE 10: DNS a domena (volitelne, 15 minut)

```
1. Kup/pripoj domenu (systeq.cz nebo tvoji)
2. Azure Portal → DNS zones → Vytvorit
   ├── Name: systeq.cz
   └── Type: Public

3. Pridej DNS zaznam:
   ├── Type: A
   ├── Name: jobs
   ├── IP: $VM_IP
   └── TTL: 3600

4. Nastav nameserver u registratore
   (cloudflare/godaddy/registru)
   ├── ns1-XX.azure-dns.com
   ├── ns2-XX.azure-dns.com
   └── (dostanes z Azure Portal → DNS zone → Overview)

5. Pockej na propagaci (1-24 hodin)
   nslookup jobs.systeq.cz
```

---

## CAST 5: Feynman reseni problemu

### 5.1 "Nemuzu se pripojit k PostgreSQL"

**Symptom:** `connection timed out`

**Feynman:** PostgreSQL je jako zamceny trezor. Musis rict "tahle IP muze vstoupit."

**Reseni:**
```powershell
# 1. Zjisti svou verejnou IP
(Invoke-WebRequest -Uri "https://api.ipify.org").Content

# 2. Pridej ji do Azure PostgreSQL firewall
# Portal → PostgreSQL → Networking → Add firewall rule
#   Rule name: AllowMyPC
#   Start IP: [tva-IP]
#   End IP: [tva-IP]

# 3. Pockej 5 minut na aplikaci pravidla
```

### 5.2 "Dashboard nacita data, ale jsou prazdna"

**Symptom:** Dashboard bezi, ale zobrazi 0 ads.

**Feynman:** Dashboard se pripoji na Azure DB, ale ta je prazdna (sync neprobehlo).

**Reseni:**
```powershell
# 1. Over ze data jsou v Azure DB
psql $CLOUD_URL -c "SELECT count(*) FROM ads;"

# 2. Pokud 0 — spust sync
python scripts/sync_to_cloud.py --cloud-url $CLOUD_URL

# 3. Over znovu
psql $CLOUD_URL -c "SELECT count(*) FROM ads;"
```

### 5.3 "Streamlit pada pri startu"

**Symptom:** `docker compose logs` ukazuje chybu.

**Feynman:** Streamlit potrebuje heslo k DB. Pokud ho neni, rekne "stop".

**Reseni:**
```bash
# 1. Zkontroluj env promenne
docker compose exec dashboard env | grep DATABASE_URL

# 2. Pokud chybi — oprav docker-compose.yml
# 3. Restart
docker compose down && docker compose up -d
```

### 5.4 "SSL chyba pri pripojeni"

**Symptom:** `sslmode is invalid` nebo `certificate verify failed`

**Feynman:** Azure vyzaduje zamceny prenos (SSL). Pokud ho nepouzivas, odmitne te.

**Reseni:**
```python
# V db.py nebo connection stringu:
DATABASE_URL = "postgresql://user:pass@server.postgres.database.azure.com:5432/db?sslmode=require"

# NEBO pro vyssi bezpecnost:
DATABASE_URL = "postgresql://user:pass@server.postgres.database.azure.com:5432/db?sslmode=verify-ca"
```

---

## CAST 6: Naklady a monitoring

### 6.1 Free tier limity (12 mesicu)

| Sluzba | Limit | Cena po limitu |
|--------|-------|----------------|
| PostgreSQL B1ms | 750h/mesic | ~$12/mesic |
| PostgreSQL storage | 32 GB | ~$0.115/GB/mesic |
| VM B1S | 750h/mesic | ~$7.5/mesic |
| Managed Disk | 30 GB | ~$1.5/mesic |
| **Celkem po 12 mesicich** | | **~$21/mesic** |

### 6.2 Monitoring nakladu

```
1. Azure Portal → Cost Management + Billing
2. Cost alerts:
   ├── Nastav alert na $0 (dostanes email kdykoliv neco stoji)
   └── Budget: $0 (free tier) → notify at 80%, 100%

3. Prehled:
   ├── Cost analysis: kolik co stoji
   ├── Budgets: nastaveni limitu
   └── Advisor: doporuceni na usporu
```

### 6.3 Jak se vyhnout platbe

```powershell
# 1. Nastav budget alert na $0
# Portal → Cost Management → Budgets → Add

# 2. Kazdy mesic zkontroluj usage
# Portal → Subscriptions → Usage + quotas

# 3. Pokud nechces platit po 12 mesicich:
#   a) Presun na Supabase/Neon (kdyz vyhovuje)
#   b) Zrus Azure resources
#   c) Presun na nizsi SKU (jestli to staci)
```

---

## CAST 7: Azure CLI zaklady (bonus)

### 7.1 Instalace Azure CLI

```powershell
# Windows
winget install Microsoft.AzureCLI

# Overeni
az version
az login
```

### 7.2 Uzitecne prikazy

```powershell
# Přehled resources
az resource list --resource-group rg-mcpjobs-prod --output table

# Stav PostgreSQL
az postgres flexible-server show \
  --resource-group rg-mcpjobs-prod \
  --name mcpjobs-pgsql \
  --query "{state:state, fqdn:fullyQualifiedDomainName}"

# Stav VM
az vm get-instance-view \
  --resource-group rg-mcpjobs-prod \
  --name vm-mcpjobs-dashboard \
  --query "powerState"

# Firewall rules
az postgres flexible-server firewall-rule list \
  --resource-group rg-mcpjobs-prod \
  --name mcpjobs-pgsql --output table

# Cisteni (po testovani)
az group delete --name rg-mcpjobs-prod --yes --no-wait
```

---

## CAST 8: Checklist pred deployem

```
□ Azure ucet vytvoren + $200 kredit aktivni
□ PostgreSQL server vytvoren (B1ms, West Europe, 32 GB)
□ Schema inicializovano (schema.sql)
□ Data syncnuta (sync_to_cloud.py, 187 ads)
□ VM vytvorena (B1S, Ubuntu 24.04, SSH key)
□ Docker nainstalovan na VM
□ Streamlit dashboard naloadovan a bezi
□ NSG pravidla nastavena (22, 80, 443)
□ PostgreSQL firewall: AllowMyPC + AllowAzureServices
□ Healthcheck OK: curl http://VM_IP:8501/_stcore/health
□ Budget alert na $0 nastaven
```

---

## CESTA DALE

```
Azure deploy (tento dokument)
  ↓
AZ-900 priprava (Microsoft Learn AZ-900 path)
  ↓
AZ-900 certifikace (~10-15 hod)
  ↓
Dalsi Azure sluzby:
  ├── Azure Functions (serverless ETL)
  ├── Azure DevOps (CI/CD pipeline)
  ├── Azure Monitor (logging, alerts)
  └── Azure App Service (alternativa k VM)
```

---

*Tento dokument je zivy. Aktualizace po kazdem uspesnem kroku.*
