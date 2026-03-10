import requests
import threading
import time
import random
from datetime import datetime
from test_utils import BaseClient, SERVER_URL, NUM_CLIENTS, VERIFY_SSL, CLIMBER_BIBS, BLOC_TAGS, print_stats_header, print_stats_summary

REQUESTS_PER_CLIENT = 20  # Nombre de cycles scan QR par client
 
 
class AndroidClient(BaseClient):
    def __init__(self, client_id):
        super().__init__(client_id)
        self.stats = {
            'climber_success': 0,
            'climber_fail': 0,
            'bloc_success': 0,
            'bloc_fail': 0,
            'validation_success': 0,
            'validation_fail': 0,
            'total_time': 0
        }
   
    def check_climber_with_log(self, bib):
        """Verify climber exists with logging"""
        success, duration = super().check_climber(bib)
        if success:
            self.stats['climber_success'] += 1
            self.log(f"✓ Climber {bib} OK ({duration:.2f}s)")
        else:
            self.stats['climber_fail'] += 1
            self.log(f"✗ Climber {bib} FAILED")
        return success
   
    def check_bloc_with_log(self, tag):
        """Verify bloc exists with logging"""
        success, duration = super().check_bloc(tag)
        if success:
            self.stats['bloc_success'] += 1
            self.log(f"✓ Bloc {tag} OK ({duration:.2f}s)")
        else:
            self.stats['bloc_fail'] += 1
            self.log(f"✗ Bloc {tag} FAILED")
        return success
   
    def register_success_with_log(self, bib, tag):
        """Register success with logging"""
        success, duration = super().register_success(bib, tag)
        if success:
            self.stats['validation_success'] += 1
            self.log(f"✓ SUCCESS {bib} → {tag} OK ({duration:.2f}s)")
        else:
            self.stats['validation_fail'] += 1
            self.log(f"✗ SUCCESS {bib} → {tag} FAILED")
        return success
   
    def simulate_user_flow(self):
        """Simule le flux complet d'un utilisateur"""
        for i in range(REQUESTS_PER_CLIENT):
            # Simule le temps de scan QR (1-3 secondes)
            time.sleep(random.uniform(0.001, 0.1))
           
            # 1. Scan QR grimpeur
            climber_bib = random.choice(CLIMBER_BIBS)
            if not self.check_climber_with_log(climber_bib):
                continue
           
            # Délai avant scan du bloc
            time.sleep(random.uniform(0.001, 0.1))
           
            # 2. Scan QR bloc
            bloc_tag = random.choice(BLOC_TAGS)
            if not self.check_bloc_with_log(bloc_tag):
                continue
           
            # Délai avant validation
            time.sleep(random.uniform(0.001, 0.1))
           
            # 3. Validation
            self.register_success_with_log(climber_bib, bloc_tag)
           
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
   
    print_stats_header("GLOBAL STATISTICS")
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
    
    print_stats_summary(total_stats, total_time)

if __name__ == "__main__":
    run_load_test()