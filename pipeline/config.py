"""
Everything you might want to tweak lives in this one file.

- Which companies we pull from (and on which hiring platform)
- The fixed list of role categories the LLM must choose from
- The list of cities the LLM must normalise to
- Which LLM model we use and what it would cost on the paid tier
"""

# ---------------------------------------------------------------------------
# 1. SOURCES
# ---------------------------------------------------------------------------
# Every source below is an *official public API* that the hiring platform
# publishes so that job boards can list a company's openings. We never scrape
# HTML pages, and we never touch sites whose terms forbid automated access
# (LinkedIn, Naukri, Internshala, Indeed ...).
#
# The value is the company's "board token" / slug on that platform, which you
# can read straight from the company's careers URL, e.g.
#   https://boards.greenhouse.io/postman   ->  "postman"
#   https://jobs.lever.co/cred             ->  "cred"
#   https://jobs.ashbyhq.com/rippling      ->  "rippling"
# A wrong slug is harmless: the fetcher logs it and moves on.

GREENHOUSE = [
    "postman", "phonepe", "groww", "razorpaysoftwareprivatelimited", "meesho",
    "inmobi", "sprinklr", "browserstack", "druva", "chargebee", "hasura",
    "smallcase", "innovaccer", "highradius", "mindtickle", "whatfix",
    "games24x7", "dream11", "mpl", "sharechat", "urbancompany", "lenskart",
    "acko", "cars24", "spinny", "rapido", "porter", "delhivery", "licious",
    "juspay", "cashfree", "zeta", "slice", "jupiter", "upgrad", "unacademy",
    "physicswallah", "scaler", "leadsquared", "darwinbox", "rocketlane",
    "sprinto", "zluri", "atlan", "perfios", "setu", "khatabook", "nykaa",
    "policybazaar", "paytm", "mobikwik", "oyo", "groupon", "stripe",
    "databricks", "coinbase", "gitlab", "cloudflare", "mongodb", "elastic",
    "twilio", "okta", "datadog", "rubrik", "nutanix", "samsara", "hubspot",
    "airbnb", "pinterest", "dropbox", "zscaler", "toast", "intercom",
    "commvault", "sumologic", "confluent", "cohesity", "tekion", "uniphore",
    "observeai", "gupshup", "yellowai", "haptik", "vedantu", "cuemath",
    "zomato", "swiggy", "bharatpe", "groyyo", "zetwerk", "ofbusiness",
    "thoughtworks", "moengage", "clevertap", "netcore", "ixigo", "cleartrip",
    "agoda", "sahaj", "gojek", "tide", "transferwise", "wise", "grab", "turing",
    "deepintent", "exotel", "medianet", "netomi", "fractal", "tigeranalytics",
    "mu-sigma", "quantiphi", "sigmoid", "lummo", "kotak", "angelone", "dhan",
    "zerodha", "indmoney", "navi", "ola", "olaelectric", "ather", "boat",
    "mamaearth", "sugar", "purplle", "firstcry", "pepperfry", "urbanladder",
]

LEVER = [
    "cred", "upstox", "jar", "fampay", "cleartax", "spotdraft", "plivo",
    "hackerrank", "dunzo", "zetwerk", "bharatpe", "meesho", "paytm", "zeta",
    "nobroker", "pharmeasy", "udaan", "infra-market", "classplus", "eloelo",
    "mindtickle", "lendingkart", "ola", "mfine", "kreditbee", "uni", "pocketfm",
    "kuku", "frontier", "glance", "inmobi", "rebel-foods", "zepto", "dukaan",
    "teachmint", "seekho", "simpl", "smallcase", "skit", "observe", "toplyne",
    "wingify", "vymo", "leena", "almabase", "gojek", "binance", "palantir",
]

ASHBY = [
    "zepto", "rippling", "sarvam", "plum", "composio", "atlan", "deel",
    "notion", "linear", "ramp", "cred", "smallest", "neysa", "pazcare",
    "dodo-payments", "sprinto", "loop", "airtribe", "bhanzu", "superjoin",
    "kapture", "eightfold", "sarvam-ai", "lemnisk", "headout", "multiplier",
]

# More Indian companies whose platform we're not sure of: tried on all three above.
ANY_PLATFORM = [
    "sharechat", "unacademy", "vedantu", "upgrad", "byjus", "jupiter-money", "khatabook",
    "rapido", "spinny", "practo", "healthifyme", "curefit", "freecharge", "simplilearn",
    "greyorange", "hevodata", "ninjacart", "zoomcar", "coindcx", "coinswitch", "mpl",
    "winzo", "zupee", "rooter", "apna", "cuemath", "leapfinance", "stashfin", "moneyview",
    "shiprocket", "blackbuck", "rivigo", "magicpin", "eightfold", "devrev", "parkplus",
    "jar-app", "fi", "fimoney", "scapia", "kuku-fm", "stockgro", "smallcase", "zerodha",
    "groww", "dream11", "games24x7", "nobroker", "housing", "squareyards", "cars24",
    "droom", "bluestone", "caratlane", "boat-lifestyle", "mokobara", "snitch", "bewakoof",
    "thesouledstore", "wakefit", "sleepyowl", "rage-coffee", "zetwerk", "moglix",
    "udaan", "jumbotail", "dealshare", "citymall", "meesho", "shopsy", "ajio",
    "tata1mg", "pharmeasy", "netmeds", "medibuddy", "innovaccer", "qure-ai", "niramai",
    "sigtuple", "tricog", "ultrahuman", "zeno-health", "even", "plum", "loop-health",
    "onsurity", "ditto", "turtlemint", "renewbuy", "insurancedekho", "coverfox",
    "postman", "browserstack", "freshworks", "zoho", "chargebee", "clevertap",
    "moengage", "webengage", "netcore", "gupshup", "exotel", "ozonetel", "haptik",
    "yellow-ai", "verloop", "observe-ai", "uniphore", "skit-ai", "sarvam-ai", "krutrim",
    "glean", "atlassian", "canva", "rippling", "deel", "remote", "toptal",
]

# SmartRecruiters company identifiers (from jobs.smartrecruiters.com/<id>)
SMARTRECRUITERS = [
    "Visa", "BoschGroup", "ServiceNow", "Freshworks", "Ubisoft2", "Equinix",
    "WesternDigital", "Sodexo", "McAfee", "Experian", "Abbott", "Canva",
    "NielsenIQ", "PublicisGroupe", "Sutherland", "TaskUs", "Wipro", "Capgemini",
    "Infosys", "HCLTech", "LTIMindtree", "TechMahindra", "Genpact", "WNS",
    "Concentrix", "Teleperformance", "Siemens", "SiemensHealthineers", "Philips",
    "Unilever", "Nestle", "Lenovo", "IKEA", "Decathlon", "Hitachi", "Mphasis",
    "Persistent", "Zensar", "Hexaware", "Coforge", "KPMG", "Deloitte", "EY", "PwC",
    "Continental", "ZF", "Valeo", "SchneiderElectric", "ABB", "Honeywell",
    "Mercedes-Benz", "Skoda", "Volvo", "Ericsson", "Nokia", "Allegis", "Randstad",
    "Adecco", "Turing", "BrowserStack", "Paytm", "Swiggy", "Zomato", "Myntra",
]

# Workable account slugs (from apply.workable.com/<slug>)
WORKABLE = [
    "razorpay", "groww", "zepto", "jupiter-money", "fi-money", "smallcase",
    "springworks", "kissflow", "zoho", "chargebee", "hevo-data", "signzy",
    "wysa", "tracxn", "fyle", "pixis", "vahan", "loco", "stockgro", "bureau",
    "almabase", "toddle", "sarvam-ai", "nference", "lucidity", "zenduty",
]

# Recruitee company slugs (from <slug>.recruitee.com)
RECRUITEE = [
    "hackerearth", "instamojo", "unstop", "skillvertex", "codingninjas",
    "airmeet", "superops", "facilio", "ultrahuman", "zolve", "eloelo",
]

# Jooble India: OPTIONAL, free key by email. Only used if JOOBLE_API_KEY is set.
JOOBLE_QUERIES = ["fresher", "internship", "graduate trainee", "entry level", "0-1 years"]
JOOBLE_PAGES_PER_QUERY = 3

# Adzuna India: OPTIONAL. Full API access needs a card on file, so the pipeline
# runs fine without it and only uses it if ADZUNA_APP_ID/KEY secrets exist.
# The free test plan allows only 25 calls IN TOTAL, so we spend at most 2 per run.
# When the quota runs out the calls fail quietly and the run carries on.
# Two different queries each day (rotating), so the archive keeps growing in variety.
ADZUNA_QUERIES = ["fresher internship", "graduate trainee", "entry level fresher",
                  "intern", "junior associate fresher", "campus hiring"]
ADZUNA_PAGES_PER_QUERY = 1          # 50 results per page
ADZUNA_MAX_CALLS_PER_RUN = 2
ADZUNA_MAX_DAYS_OLD = 30

# ---------------------------------------------------------------------------
# 2. TAXONOMY  (the LLM must pick exactly one of these)
# ---------------------------------------------------------------------------
ROLES = [
    "Software Engineering",
    "Data & Analytics",
    "AI / ML",
    "Product",
    "Design",
    "Marketing",
    "Sales & Business Development",
    "Operations & Supply Chain",
    "Finance & Accounting",
    "HR & Recruiting",
    "Customer Success & Support",
    "Content & Communications",
    "Consulting & Strategy",
    "Hardware & Electronics",
    "Other",
]

# Canonical cities. Anything spelled differently ("Bangalore", "Gurgaon",
# "Bombay", "New Delhi") must be mapped to one of these by the LLM.
CITIES = [
    "Bengaluru", "Mumbai", "Delhi", "Gurugram", "Noida", "Hyderabad", "Pune",
    "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Kochi", "Chandigarh",
    "Indore", "Coimbatore", "Thiruvananthapuram", "Remote", "Other India",
]

LEVELS = ["Internship", "Fresher", "Early career", "Not fresher", "Not a job"]

# ---------------------------------------------------------------------------
# 3. LLM
# ---------------------------------------------------------------------------
# First choice, then fallbacks. Google retires model names over time; if none of
# these exist the tagger asks the API which models are available and picks a
# Flash-Lite (cheapest) model by itself, and logs which one it used.
GEMINI_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-flash-lite-latest",
                 "gemini-3.5-flash", "gemini-flash-latest"]
BATCH_SIZE = 40                     # posts per LLM call (fewer calls = fits the free daily quota)
SECONDS_BETWEEN_CALLS = 4.5         # free tier allows ~15 requests/minute

# What each model costs on Google's PAID tier, in USD per 1M tokens (input, output).
# We run on the free tier (bill = $0), but report what it *would* cost at scale.
# Source: ai.google.dev/gemini-api/docs/pricing  (checked 18 Nov 2026)
PRICES = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.5-flash": (1.50, 9.00),
}
DEFAULT_PRICE = (0.25, 1.50)   # used if the API picked a model not listed above
USD_TO_INR = 84.0
