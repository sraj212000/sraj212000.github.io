import sys
from core import run_search, normalise_text

def get_user_inputs():
    print("=== Dynamic DOI Extractor ===")

    print("\nEnter keywords separated by '+' (e.g., CVD+Growth+2D+DFT):")
    try:
        raw_input = input("> ").strip()
    except EOFError:
        return ["test"], 1, 10 # Default for non-interactive runs

    keyword_input = normalise_text(raw_input) # reusing normalise for some basic cleaning if needed, though split is better

    if not raw_input:
        print("Error: No keywords provided.")
        sys.exit(1)

    keywords = [k.strip() for k in raw_input.split('+') if k.strip()]

    print(f"\nThere are {len(keywords)} keywords: {keywords}")
    print("Enter the minimum number of keywords required to match (Threshold):")
    try:
        threshold = int(input("> ").strip())
        if threshold < 1: threshold = 1
    except ValueError:
        threshold = 1

    print("\nEnter the maximum number of PAPERS you want to save (Output Limit):")
    try:
        output_limit = int(input("> ").strip())
        if output_limit < 1: output_limit = 100
    except ValueError:
        output_limit = 100

    return keywords, threshold, output_limit


def main():
    keywords, threshold, output_limit = get_user_inputs()

    print(f"\n[Configuration]")
    print(f"Keywords: {keywords}")
    print(f"Threshold: Match at least {threshold} keywords")
    print(f"Output Target: {output_limit} papers")

    print(f"\nStarting search...")

    def progress_callback(scanned, matches):
        if scanned % 50 == 0:
            sys.stdout.write(f"\rScanned: {scanned} | Matches: {matches}")
            sys.stdout.flush()

    df = run_search(keywords, threshold, output_limit, progress_callback)
    
    print("\n\nSearch complete.")
    print(f"Total relevant papers found: {len(df)}")

    if not df.empty:
        output_filename = "search_results.xlsx"
        print(f"Saving to '{output_filename}'...")
        try:
            df.to_excel(output_filename, index=False)
            print(f"✅ Successfully saved {len(df)} papers")
        except Exception as e:
            print(f"❌ Excel save failed: {e}")
            df.to_csv("search_results.csv", index=False)
            print("Saved as CSV instead.")
    else:
        print("No papers found matching your criteria.")

if __name__ == "__main__":
    main()


