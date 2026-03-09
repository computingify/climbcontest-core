import requests
import threading
import time
import random
from datetime import datetime
 
# Configuration
SERVER_URL = "https://climbcontestserver.onrender.com" #"https://127.0.0.1:5007"
NUM_CLIENTS = 20
REQUESTS_PER_CLIENT = 20  # Nombre de cycles scan QR par client
VERIFY_SSL = True  # False pour cert auto-signé en local
 
# Données de test
CLIMBER_BIBS = [f"{i:03d}" for i in range(1, 100)]
BLOC_TAGS = ["ZJ6", "ZJ24", "ZJ25", "ZJ26", "ZJ9", "DJ10", "DV21", "DJ8", "DV7", "CM13", "CB11", "CV14", "CR3", "CJ23", "AB15", "AJ1", "AM12", "AJ11", "AV1", "EB1", "EB8", "EJ18", "EM5", "EJ17", "FN2", "FV15", "GV12", "GR16", "GB4", "GV6", "IJ7", "IM8", "IB12", "IJ22", "IV16", "JB7", "JJ15", "JB6", "JJ19", "KM9", "KM4", "KV20", "KJ4", "LV4", "LJ5", "LJ16", "MV11", "MJ14", "MM7", "NB2"]
 
class AndroidClient:
    def __init__(self, client_id):
        self.client_id = client_id
        self.session = requests.Session()
        self.stats = {
            'climber_success': 0,
            'climber_fail': 0,
            'bloc_success': 0,
            'bloc_fail': 0,
            'validation_success': 0,
            'validation_fail': 0,
            'total_time': 0
        }
   
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Client {self.client_id:02d}: {message}")
   
    def check_climber(self, bib):
        """Simule le scan du QR code grimpeur"""
        try:
            start = time.time()
            response = self.session.post(
                f"{SERVER_URL}/api/v2/contest/climber/name",
                json={"id": bib},
                timeout=5,
                verify=VERIFY_SSL
            )
            duration = time.time() - start
           
            if response.status_code == 201:
                self.stats['climber_success'] += 1
                self.log(f"✓ Climber {bib} OK ({duration:.2f}s)")
                return True
            else:
                self.stats['climber_fail'] += 1
                self.log(f"✗ Climber {bib} FAILED: {response.status_code} ({duration:.2f}s)")
                return False
        except Exception as e:
            self.stats['climber_fail'] += 1
            self.log(f"✗ Climber {bib} ERROR: {e}")
            return False
   
    def check_bloc(self, tag):
        """Simule le scan du QR code bloc"""
        try:
            start = time.time()
            response = self.session.post(
                f"{SERVER_URL}/api/v2/contest/bloc/name",
                json={"id": tag},
                timeout=5,
                verify=VERIFY_SSL
            )
            duration = time.time() - start
           
            if response.status_code == 201:
                self.stats['bloc_success'] += 1
                self.log(f"✓ Bloc {tag} OK ({duration:.2f}s)")
                return True
            else:
                self.stats['bloc_fail'] += 1
                self.log(f"✗ Bloc {tag} FAILED: {response.status_code} ({duration:.2f}s)")
                return False
        except Exception as e:
            self.stats['bloc_fail'] += 1
            self.log(f"✗ Bloc {tag} ERROR: {e}")
            return False
   
    def register_success(self, bib, tag):
        """Simule la validation"""
        try:
            start = time.time()
            response = self.session.post(
                f"{SERVER_URL}/api/v2/contest/success",
                json={"bib": bib, "bloc": tag},
                timeout=10,
                verify=VERIFY_SSL
            )
            duration = time.time() - start
           
            if response.status_code == 201:
                self.stats['validation_success'] += 1
                self.log(f"✓ SUCCESS {bib} → {tag} OK ({duration:.2f}s)")
                return True
            else:
                self.stats['validation_fail'] += 1
                self.log(f"✗ SUCCESS {bib} → {tag} FAILED: {response.status_code} ({duration:.2f}s)")
                return False
        except Exception as e:
            self.stats['validation_fail'] += 1
            self.log(f"✗ SUCCESS {bib} → {tag} ERROR: {e}")
            return False
   
    def simulate_user_flow(self):
        """Simule le flux complet d'un utilisateur"""
        for i in range(REQUESTS_PER_CLIENT):
            # Simule le temps de scan QR (1-3 secondes)
            time.sleep(random.uniform(0.001, 0.1))
           
            # 1. Scan QR grimpeur
            climber_bib = random.choice(CLIMBER_BIBS)
            if not self.check_climber(climber_bib):
                continue
           
            # Délai avant scan du bloc
            time.sleep(random.uniform(0.001, 0.1))
           
            # 2. Scan QR bloc
            bloc_tag = random.choice(BLOC_TAGS)
            if not self.check_bloc(bloc_tag):
                continue
           
            # Délai avant validation
            time.sleep(random.uniform(0.001, 0.1))
           
            # 3. Validation
            self.register_success(climber_bib, bloc_tag)
           
            # Pause entre deux cycles complets
            time.sleep(random.uniform(0.1, 0.5))
   
    def run(self):
        """Lance la simulation pour ce client"""
        self.log("🚀 STARTED")
        start_time = time.time()
       
        try:
            self.simulate_user_flow()
        except KeyboardInterrupt:
            self.log("⚠️ INTERRUPTED")
        finally:
            self.stats['total_time'] = time.time() - start_time
            self.log(f"📊 FINISHED - Stats: {self.stats}")
 
def run_load_test():
    """Lance le test de charge avec plusieurs clients"""
    print("="*80)
    print(f"🏔️  CLIMBING CONTEST - LOAD TEST")
    print(f"   Clients: {NUM_CLIENTS}")
    print(f"   Requests per client: {REQUESTS_PER_CLIENT}")
    print(f"   Server: {SERVER_URL}")
    print("="*80)
    print()
   
    # Désactive les warnings SSL si nécessaire
    if not VERIFY_SSL:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
   
    # Créer les clients
    clients = [AndroidClient(i) for i in range(1, NUM_CLIENTS + 1)]
   
    # Lancer tous les clients en parallèle
    threads = []
    start_time = time.time()
   
    for client in clients:
        thread = threading.Thread(target=client.run)
        thread.start()
        threads.append(thread)
        # Petit délai pour étaler le démarrage (simule des users qui ne démarrent pas exactement ensemble)
        time.sleep(random.uniform(0.1, 0.5))
   
    # Attendre que tous les threads finissent
    for thread in threads:
        thread.join()
   
    total_time = time.time() - start_time
   
    # Afficher les statistiques globales
    print()
    print("="*80)
    print("📈 GLOBAL STATISTICS")
    print("="*80)
   
    total_stats = {
        'climber_success': 0,
        'climber_fail': 0,
        'bloc_success': 0,
        'bloc_fail': 0,
        'validation_success': 0,
        'validation_fail': 0
    }
   
    for client in clients:
        for key in total_stats.keys():
            total_stats[key] += client.stats[key]
   
    print(f"Total time: {total_time:.2f}s")
    print(f"\nClimber checks:")
    print(f"  ✓ Success: {total_stats['climber_success']}")
    print(f"  ✗ Failed:  {total_stats['climber_fail']}")
   
    print(f"\nBloc checks:")
    print(f"  ✓ Success: {total_stats['bloc_success']}")
    print(f"  ✗ Failed:  {total_stats['bloc_fail']}")
   
    print(f"\nValidations:")
    print(f"  ✓ Success: {total_stats['validation_success']}")
    print(f"  ✗ Failed:  {total_stats['validation_fail']}")
   
    total_requests = sum(total_stats.values())
    failed_requests = total_stats['climber_fail'] + total_stats['bloc_fail'] + total_stats['validation_fail']
    success_rate = ((total_requests - failed_requests) / total_requests * 100) if total_requests > 0 else 0
   
    print(f"\n{'='*80}")
    print(f"Success rate: {success_rate:.2f}%")
    print(f"Total requests: {total_requests}")
    print(f"Failed requests: {failed_requests}")
    print(f"Requests/second: {total_requests/total_time:.2f}")
    print("="*80)
 
if __name__ == "__main__":
    run_load_test()