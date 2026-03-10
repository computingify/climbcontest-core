"""
Shared utilities for climbing contest test suites
"""
import requests
import time
from datetime import datetime

# Configuration
SERVER_URL = "https://climbcontestserver.onrender.com"  # or "https://127.0.0.1:5007" for local
NUM_CLIENTS = 20
VERIFY_SSL = True  # False for self-signed cert locally

# Test data
CLIMBER_BIBS = [f"{i:03d}" for i in range(1, 100)]
BLOC_TAGS = ["ZJ6", "ZJ24", "ZJ25", "ZJ26", "ZJ9", "DJ10", "DV21", "DJ8", "DV7", "CM13", "CB11", "CV14", "CR3", "CJ23", "AB15", "AJ1", "AM12", "AJ11", "AV1", "EB1", "EB8", "EJ18", "EM5", "EJ17", "FN2", "FV15", "GV12", "GR16", "GB4", "GV6", "IJ7", "IM8", "IB12", "IJ22", "IV16", "JB7", "JJ15", "JB6", "JJ19", "KM9", "KM4", "KV20", "KJ4", "LV4", "LJ5", "LJ16", "MV11", "MJ14", "MM7", "NB2"]


class BaseClient:
    """Base client with common HTTP methods for all test clients"""
    
    def __init__(self, client_id):
        self.client_id = client_id
        self.session = requests.Session()
    
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Client {self.client_id:02d}: {message}")
    
    def check_climber(self, bib):
        """Verify climber exists"""
        try:
            start = time.time()
            response = self.session.post(
                f"{SERVER_URL}/api/v2/contest/climber/name",
                json={"id": bib},
                timeout=5,
                verify=VERIFY_SSL
            )
            duration = time.time() - start
            return response.status_code == 201, duration
        except Exception as e:
            self.log(f"❌ Climber {bib} ERROR: {e}")
            return False, 0
    
    def check_bloc(self, tag):
        """Verify bloc exists"""
        try:
            start = time.time()
            response = self.session.post(
                f"{SERVER_URL}/api/v2/contest/bloc/name",
                json={"id": tag},
                timeout=5,
                verify=VERIFY_SSL
            )
            duration = time.time() - start
            return response.status_code == 201, duration
        except Exception as e:
            self.log(f"❌ Bloc {tag} ERROR: {e}")
            return False, 0
    
    def register_success(self, bib, tag):
        """Register success for climber on bloc"""
        try:
            start = time.time()
            response = self.session.post(
                f"{SERVER_URL}/api/v2/contest/success",
                json={"bib": bib, "bloc": tag},
                timeout=10,
                verify=VERIFY_SSL
            )
            duration = time.time() - start
            return response.status_code == 201, duration
        except Exception as e:
            self.log(f"❌ Success {bib}→{tag} ERROR: {e}")
            return False, 0


def print_stats_header(title, details=None):
    """Print formatted statistics header"""
    print()
    print("="*80)
    print(f"📈 {title}")
    if details:
        for key, value in details.items():
            print(f"   {key}: {value}")
    print("="*80)


def print_stats_summary(total_stats, total_time, total_requests=None):
    """Print formatted statistics summary"""
    print(f"Total time: {total_time:.2f}s")
    
    if total_requests is None:
        total_requests = sum(total_stats.values())
    
    failed_requests = 0
    for key, value in total_stats.items():
        if 'fail' in key:
            failed_requests += value
    
    success_rate = ((total_requests - failed_requests) / total_requests * 100) if total_requests > 0 else 0
    
    print(f"\n{'='*80}")
    print(f"Success rate: {success_rate:.2f}%")
    print(f"Total requests: {total_requests}")
    print(f"Failed requests: {failed_requests}")
    print(f"Requests/second: {total_requests/total_time:.2f}")
    print("="*80)
