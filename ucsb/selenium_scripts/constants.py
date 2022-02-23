CHROME_BINARY_LOCATION = "/usr/bin/chromium-browser"

CHROME_ADBLOCK_LOCATION= "/home/ec2-user/Downloads/extension_3_7_0_0.crx" # note - couldn't get this to work

FIREFOX_BINARY_LOCATION = "/usr/bin/firefox"

FIREFOX_PROFILE_LOCATION = "./profiles"

ERROR_REPORT_DIR = "./error_reports"

METADATA_DIR = "./metadata"

KNOWN_IP_LIST_FN = "known_ips.pkl"

TRACES_DIR = "./throughput_traces/traces"

PCAP_DIR = "./pcaps"

LOG_DIR = "./logs"

FIGURE_DIR = "./figures"

MODEL_DIR = "./models"

SSL_KEYLOG_FILE ="./ssl_keys/sslkeylog.log"

N_FLOWS = 10 # TODO -- replace with by-service (one model for each service)

HISTORY_LENGTH = 50 # TODO -- replace with by-service

GET_REQUEST_SIZE = 300 # bytes

AVAILABLE_BW = 2.0e6 # bps



# IPs internal to the observed network

INTERNAL_IPS = ["172.31.30.176"]

INTERNAL_NETWORKS = ["172.31.30.0/24", "10.0.0.0/8"]



INTERFACE =  "ens5"

ASN_LIST = ["GOOGLE", "NETFLIX-ASN", "AMAZON-AES", "AKAMAI-AS", "FACEBOOK", "JUSTINTV", "OTHER"]

ASN_LIST = {k:i for i, k in enumerate(ASN_LIST)}

MAX_TIME = 300 # max time for a stream to be active

NETFLIX_PROFILE_INDEX = 3 # number in the list of netflix profiles on the accouont you should use (zero indexed)

T_INTERVAL = 1 # interval over which to bin statistics

TOTAL_N_CHANNELS = 7 # number of channels in a temporal statistics image (basically # types of features  *  2)

VIDEO_SERVICES = ["twitch", "netflix", "youtube"] # it is useful to have these in the same order in all classes when possible





# Normalizations for features

BYTE_TRANSFER_NORM = float(.5e6)

DUP_ACK_NORM = 30



# tcp port over which zmq connection is established

ZMQ_PORT = 5558
