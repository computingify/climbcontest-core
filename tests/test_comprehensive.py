import requests
import threading
import time
import random
from datetime import datetime
from test_utils import BaseClient, SERVER_URL, VERIFY_SSL, CLIMBER_BIBS, BLOC_TAGS, print_stats_header, print_stats_summary

NUM_CLIENTS = 99  # Number of climbers to test (each will try all blocs)
class ComprehensiveClient(BaseClient):
    """Client that tests one specific climber against ALL blocs"""
    def __init__(self, client_id, climber_bib):
        super().__init__(client_id)
        self.climber_bib = climber_bib
        self.stats = {
            'climber_check': 0,
            'climber_check_fail': 0,
            'bloc_checks': 0,
            'bloc_checks_fail': 0,
            'validations': 0,
            'validations_fail': 0,
            'total_time': 0
        }

    def log(self, message):
        """Override log to include climber BIB"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Client {self.client_id:02d} (Climber {self.climber_bib}): {message}")

    def check_climber_once(self):
        """Verify climber exists"""
        success, duration = super().check_climber(self.climber_bib)
        if success:
            self.stats['climber_check'] += 1
            self.log(f"✓ Climber {self.climber_bib} verified ({duration:.2f}s)")
        else:
            self.stats['climber_check_fail'] += 1
            self.log(f"✗ Climber {self.climber_bib} FAILED")
        return success

    def check_bloc_with_stats(self, tag):
        """Verify bloc exists"""
        success, duration = super().check_bloc(tag)
        if success:
            self.stats['bloc_checks'] += 1
        else:
            self.stats['bloc_checks_fail'] += 1
        return success

    def register_success_with_stats(self, tag):
        """Register success for this climber on this bloc"""
        success, duration = super().register_success(self.climber_bib, tag)
        if success:
            self.stats['validations'] += 1
            self.log(f"✓ SUCCESS {self.climber_bib} → {tag} ({duration:.2f}s)")
        else:
            self.stats['validations_fail'] += 1
            self.log(f"✗ SUCCESS {self.climber_bib} → {tag} FAILED")
        return success
    
    def test_all_blocs(self):
        """Test this climber against ALL blocs"""
        # First verify climber exists
        if not self.check_climber_once():
            self.log("❌ Cannot proceed - climber verification failed")
            return

        # Now test all blocs
        for bloc_tag in BLOC_TAGS:
            time.sleep(random.uniform(0.01, 0.05))  # Small delay between bloc tests

            if self.check_bloc_with_stats(bloc_tag):
                self.register_success_with_stats(bloc_tag)
            else:
                self.log(f"⚠️ Bloc {bloc_tag} verification failed, skipping registration")

    def run(self):
        """Launch test for this climber"""
        self.log("🚀 STARTED - Testing all blocs")
        start_time = time.time()

        try:
            self.test_all_blocs()
        except KeyboardInterrupt:
            self.log("⚠️ INTERRUPTED")
        finally:
            self.stats['total_time'] = time.time() - start_time
            self.log(f"✅ FINISHED - Stats: {self.stats}")


def run_comprehensive_test():
    """Run comprehensive test: 20 climbers, each tries ALL blocs"""
    print("="*80)
    print(f"🏔️  COMPREHENSIVE CLIMBING CONTEST TEST")
    print(f"   Clients: {NUM_CLIENTS}")
    print(f"   Blocs per climber: {len(BLOC_TAGS)}")
    print(f"   Total validations: {NUM_CLIENTS * len(BLOC_TAGS)}")
    print(f"   Server: {SERVER_URL}")
    print("="*80)
    print()

    # Disable SSL warnings if needed
    if not VERIFY_SSL:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Create clients - each gets a unique climber
    clients = []
    for i in range(1, NUM_CLIENTS + 1):
        climber_bib = CLIMBER_BIBS[i - 1]  # Use first N climbers
        client = ComprehensiveClient(i, climber_bib)
        clients.append(client)

    # Launch all clients in parallel
    threads = []
    start_time = time.time()

    for client in clients:
        thread = threading.Thread(target=client.run)
        thread.start()
        threads.append(thread)
        time.sleep(random.uniform(0.1, 0.3))  # Stagger start times

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    total_time = time.time() - start_time

    # Display global statistics
    total_stats = {
        'climber_check': 0,
        'climber_check_fail': 0,
        'bloc_checks': 0,
        'bloc_checks_fail': 0,
        'validations': 0,
        'validations_fail': 0
    }

    for client in clients:
        for key in total_stats.keys():
            total_stats[key] += client.stats[key]

    print_stats_header("COMPREHENSIVE TEST STATISTICS")
    print(f"Total time: {total_time:.2f}s")
    print(f"\nClimber checks:")
    print(f"  ✓ Success: {total_stats['climber_check']}")
    print(f"  ✗ Failed:  {total_stats['climber_check_fail']}")

    print(f"\nBloc checks:")
    print(f"  ✓ Success: {total_stats['bloc_checks']}")
    print(f"  ✗ Failed:  {total_stats['bloc_checks_fail']}")

    print(f"\nValidations (successes):")
    print(f"  ✓ Success: {total_stats['validations']}")
    print(f"  ✗ Failed:  {total_stats['validations_fail']}")
    print(f"  Expected: {NUM_CLIENTS * len(BLOC_TAGS)}")
    
    print_stats_summary(total_stats, total_time)


if __name__ == "__main__":
    run_comprehensive_test()
