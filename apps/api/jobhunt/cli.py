import argparse
import sys
import logging
from jobhunt.db import Database
from jobhunt.runner import JobRunner, RunnerLock, LockAcquireError

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")

def cmd_run(args, db: Database):
    runner = JobRunner(db=db)
    try:
        with RunnerLock():
            if args.keyword:
                print(f"Running search for '{args.keyword}'...")
                results = runner.run_single(
                    keyword=args.keyword,
                    area_filter=args.area or "all",
                    source_names=args.sources.split(",") if args.sources else None,
                )
            else:
                print("Running all active saved searches...")
                results = runner.run_all_active()

            if not results:
                print("No active searches to run or no sources processed.")
                return

            print("\n" + "=" * 65)
            print(f"{'Source':<12} | {'Keyword':<18} | {'Found':<6} | {'New':<5} | {'Status'}")
            print("-" * 65)
            for r in results:
                stat = r["status"]
                if r["error"]:
                    stat += f" ({r['error']})"
                print(f"{r['source']:<12} | {r['keyword']:<18} | {r['found_count']:<6} | {r['new_count']:<5} | {stat}")
            print("=" * 65)
    except LockAcquireError:
        print("[!] Another jobhunt run is currently in progress. Exiting safely.")
        sys.exit(0)

def cmd_list(args, db: Database):
    jobs = db.get_jobs(
        area=args.area,
        source=args.source,
        is_new_only=args.new_only,
        query_text=args.q,
        limit=args.limit,
    )
    if not jobs:
        print("No jobs found matching criteria.")
        return

    print(f"\nShowing {len(jobs)} jobs:\n")
    for j in jobs:
        new_badge = "[NEW] " if j["is_new"] else "      "
        area_str = f"[{j['area'].replace('_', ' ').title()}]"
        src_str = f"[{j['source'].title()}]"
        remote_str = " (Remote/Hybrid)" if j["is_remote"] else ""
        print(f"{new_badge}{src_str:<12} {area_str:<20} {j['title']} @ {j['company']}{remote_str}")
        details = []
        if j["salary"]:
            details.append(f"Gaji: {j['salary']}")
        if j["location_raw"]:
            details.append(f"Lokasi asli: {j['location_raw']}")
        if details:
            print(f"      {' | '.join(details)}")
        print(f"      Link: {j['url']} (ID: {j['id']})")
        print("-" * 75)

def cmd_searches(args, db: Database):
    action = args.search_action
    if action == "list" or not action:
        searches = db.get_searches()
        if not searches:
            print("No saved searches yet. Use: python -m jobhunt searches add <keyword>")
            return
        print(f"\n{'ID':<4} | {'Active':<7} | {'Keyword':<20} | {'Area':<18} | {'Sources'}")
        print("-" * 65)
        for s in searches:
            active_str = "YES" if s["is_active"] else "NO"
            print(f"{s['id']:<4} | {active_str:<7} | {s['keyword']:<20} | {s['area']:<18} | {s['sources']}")
        print("-" * 65)
    elif action == "add":
        new_id = db.create_search(
            keyword=args.keyword,
            area=args.area or "all",
            sources=args.sources.split(",") if args.sources else ["jobstreet", "kalibrr", "linkedin", "glints", "dealls"],
        )
        print(f"[+] Saved search #{new_id} added: '{args.keyword}' (area: {args.area or 'all'})")
    elif action == "toggle":
        searches = db.get_searches()
        match = [s for s in searches if s["id"] == args.id]
        if not match:
            print(f"[!] Search ID {args.id} not found.")
            return
        new_state = not bool(match[0]["is_active"])
        db.set_search_active(args.id, new_state)
        print(f"[*] Search #{args.id} is now {'ACTIVE' if new_state else 'INACTIVE'}")
    elif action == "remove":
        db.delete_search(args.id)
        print(f"[-] Search #{args.id} deleted.")

def cmd_seen(args, db: Database):
    if args.job_id.lower() == "all":
        db.mark_all_seen()
        print("[*] All jobs marked as seen.")
    else:
        try:
            jid = int(args.job_id)
            db.mark_job_seen(jid)
            print(f"[*] Job #{jid} marked as seen.")
        except ValueError:
            print("[!] Please provide a valid job ID or 'all'.")

def main():
    parser = argparse.ArgumentParser(description="kerjo CLI - Internal multi-site job scraper & tracker")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose debug logging")
    subparsers = parser.add_subparsers(dest="command")

    # run command
    p_run = subparsers.add_parser("run", help="Run scrapers")
    p_run.add_argument("--keyword", help="Run one-off keyword instead of saved searches")
    p_run.add_argument("--area", default="all", help="Target area filter")
    p_run.add_argument("--sources", help="Comma-separated sources (e.g. jobstreet,kalibrr)")

    # list command
    p_list = subparsers.add_parser("list", help="List collected jobs")
    p_list.add_argument("--area", help="Filter by area (e.g. jakarta_selatan, bsd, etc.)")
    p_list.add_argument("--source", help="Filter by source (e.g. jobstreet, kalibrr)")
    p_list.add_argument("--new-only", action="store_true", help="Show only NEW jobs")
    p_list.add_argument("--q", help="Search in title or company")
    p_list.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    # searches command
    p_searches = subparsers.add_parser("searches", help="Manage saved searches")
    s_sub = p_searches.add_subparsers(dest="search_action")
    s_sub.add_parser("list", help="List all saved searches")

    p_s_add = s_sub.add_parser("add", help="Add new saved search")
    p_s_add.add_argument("keyword", help="Search keyword")
    p_s_add.add_argument("--area", default="all", help="Area filter (default: all)")
    p_s_add.add_argument("--sources", help="Comma-separated sources (default: jobstreet,kalibrr)")

    p_s_tog = s_sub.add_parser("toggle", help="Toggle active state of search")
    p_s_tog.add_argument("id", type=int, help="Search ID")

    p_s_del = s_sub.add_parser("remove", help="Delete a saved search")
    p_s_del.add_argument("id", type=int, help="Search ID")

    # seen command
    p_seen = subparsers.add_parser("seen", help="Mark job(s) as seen")
    p_seen.add_argument("job_id", help="Job ID or 'all'")

    # serve command
    p_serve = subparsers.add_parser("serve", help="Start the Web UI & API server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    args = parser.parse_args()
    setup_logging(args.verbose)
    db = Database()

    if args.command == "run":
        cmd_run(args, db)
    elif args.command == "list":
        cmd_list(args, db)
    elif args.command == "searches":
        cmd_searches(args, db)
    elif args.command == "seen":
        cmd_seen(args, db)
    elif args.command == "serve":
        from jobhunt.server import run_server
        run_server(host=args.host, port=args.port)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
