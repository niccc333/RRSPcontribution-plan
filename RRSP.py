import pandas as pd

def get_combined_brackets():
    """
    Returns a sorted list of (threshold, combined_marginal_rate) for 2026.
    Merges Federal and Quebec brackets to create a unified set of marginal rates.
    """
    # 2026 Federal Brackets
    fed_brackets = [
        (258482, 0.33),
        (181440, 0.29),
        (117045, 0.26),
        (58523, 0.205),
        (0, 0.14)
    ]
    
    # 2026 Quebec Brackets
    qc_brackets = [
        (132245, 0.2575),
        (108680, 0.24),
        (54345, 0.19),
        (0, 0.14)
    ]

    # Create a set of all unique thresholds
    all_thresholds = set(f[0] for f in fed_brackets) | set(q[0] for q in qc_brackets)
    sorted_thresholds = sorted(list(all_thresholds), reverse=True)
    
    combined_brackets = []
    
    for t in sorted_thresholds:
        # Determine Fed Rate at this threshold
        f_rate = 0.0
        for ft, fr in fed_brackets:
            if t >= ft:
                f_rate = fr
                break
                
        # Determine QC Rate at this threshold
        q_rate = 0.0
        for qt, qr in qc_brackets:
            if t >= qt:
                q_rate = qr
                break
        
        # Calculate Combined Rate
        effective_fed_rate = f_rate * (1 - 0.165)
        combined_rate = effective_fed_rate + q_rate
        
        combined_brackets.append((t, combined_rate))
        
    return combined_brackets

def get_marginal_tax_rate(income, brackets):
    """
    Calculates marginal rate using the pre-calculated combined brackets.
    """
    for threshold, rate in brackets:
        if income > threshold:
            return rate
    return brackets[-1][1] # Fallback to lowest rate

def optimize_rrsp_strategy(
    current_year=2026,
    start_earning_year=2020,
    current_annual_income=25000,
    full_time_start_year=2027,
    expected_full_time_wage=85000,
    wage_growth_rate=0.03,
    employer_match_rate=0.05,
    risk_free_rate=0.05,
    retirement_income_target=60000,     # Expected taxable income in retirement
    savings_rate_gross=0.25             # Portion of gross income available for savings (increased to allow room usage)
):
    
    # Constants
    rrsp_max_limit_2026 = 33810
    limit_indexing = 0.02
    
    # Pre-calculate unified tax brackets
    combined_brackets = get_combined_brackets()
    
    # Determine retirement tax rate
    retirement_tax_rate = get_marginal_tax_rate(retirement_income_target, combined_brackets)
    
    # State variables
    data = []
    accumulated_room = 0.0
    rrsp_balance = 0.0
    
    # Simulation range
    end_year = full_time_start_year + 10
    
    # 1. Past Room Calculation
    years_worked_before_now = current_year - start_earning_year
    avg_past_income = 15000 
    accumulated_room += (avg_past_income * 0.18) * years_worked_before_now

    current_income_sim = current_annual_income
    
    for year in range(current_year, end_year + 1):
        
        # 1. Update Income
        if year >= full_time_start_year:
            if year == full_time_start_year:
                current_income_sim = expected_full_time_wage
            else:
                current_income_sim *= (1 + wage_growth_rate)
        
        # 2. Update Contribution Limits
        new_room_generated = current_income_sim * 0.18
        annual_max = rrsp_max_limit_2026 * ((1 + limit_indexing) ** (year - 2026))
        
        if new_room_generated > annual_max:
            new_room_generated = annual_max
            
        # Snapshot Total Room (Opening Balance + New)
        total_room_available = accumulated_room + new_room_generated
        
        # 3. Strategy Logic
        
        # A. Employer Match (Always take this first)
        match_contribution = current_income_sim * employer_match_rate
        
        # B. Optimization Logic (Waterfall / Fill-Down)
        # We start with taxable income and "fill" RRSP to knock down income from high brackets
        # until the marginal rate is <= retirement rate.
        
        # Max cash available for RRSP (User contribution part)
        max_user_cash = (current_income_sim * savings_rate_gross)
        cash_remaining = max_user_cash
        
        # Pay for the match first
        user_base_contribution = current_income_sim * employer_match_rate
        cash_remaining -= user_base_contribution
        
        # Contribution starts with mandatory match basis
        total_user_contribution = user_base_contribution
        
        # Current effective taxable income (before extra contributions)
        # Note: We assume the user_base_contribution is also an RRSP contribution reducing income
        current_taxable_income = current_income_sim - user_base_contribution
        
        # Calculate extra optimization
        extra_contribution = 0.0
        
        # Iterate brackets primarily to find chunks of income to shelter
        # We only care about brackets where rate > retirement_rate
        
        for threshold, rate in combined_brackets:
            if rate <= retirement_tax_rate:
                continue # No tax arbitrage benefit here
            
            # If current income is above this bracket's floor (threshold)
            if current_taxable_income > threshold:
                # Calculate how much income is in this band
                income_in_band = current_taxable_income - threshold
                
                # Determine how much we CAN contribute for this band
                # Constraints: Room, Cash
                room_remaining = total_room_available - total_user_contribution
                
                amount_to_contribute = min(income_in_band, room_remaining, cash_remaining)
                
                if amount_to_contribute > 0:
                    extra_contribution += amount_to_contribute
                    total_user_contribution += amount_to_contribute
                    cash_remaining -= amount_to_contribute
                    current_taxable_income -= amount_to_contribute # Reduce income for next iteration
                
                if cash_remaining <= 0 or (total_room_available - total_user_contribution) <= 0:
                    break
        
        # Safety check against total room (should be handled in loop, but double check)
        if total_user_contribution > total_room_available:
            total_user_contribution = total_room_available
            
        # 4. Update Balances
        accumulated_room = total_room_available - total_user_contribution
        total_inflow = total_user_contribution + match_contribution
        rrsp_balance = (rrsp_balance * (1 + risk_free_rate)) + total_inflow
        
        # 5. Calculate Tax Savings
        # To be precise, we need to calculate Tax(Original) - Tax(New)
        # Since we have logic for marginal, let's approximate or do it roughly
        # For display, approximate based on weighted average of brackets used is okay, 
        # or simplified: (User Cont * Marginal) is what the user asked for previously
        # but let's make it the "Money Saved" relative to retirement
        # Actually, standard "Tax Savings" usually means reduction in current year tax bill.
        # Let's calculate that properly? No, let's stick to the simpler sum(chunk * rate)
        
        # Re-calc precise savings from the chunks
        # effectively: sum of (amount_in_bracket * bracket_rate)
        # We can just sum it up as we go, or recalculate.
        # Let's do a quick pass to estimate savings
        # actually marginal_rate at start is useful for display
        start_marginal_rate = get_marginal_tax_rate(current_income_sim, combined_brackets)
        
        # Simple tax savings calc:
        # We reduced taxable income from X to Y. 
        # Savings = Tax(X) - Tax(Y). 
        # Let's just approximate for the display to keep it simple unless requested otherwise.
        # The user said "optimizes money saved", which implies the strategy, not necessarily the column.
        # I will leave Tax Savings as a simple calc for now or simple "Effective Rate * Contribution" 
        # but since we spanned brackets, better to be (Contribution * Avg Rate of those brackets)
        # Let's just use the `extra_contribution` logic to track savings if possible.
        # Re-simplifying for display:
        tax_savings = 0.0
        temp_income = current_income_sim
        remaining_contrib_to_account = total_user_contribution
        for threshold, rate in combined_brackets:
            if temp_income > threshold:
                chunk = min(temp_income - threshold, remaining_contrib_to_account)
                tax_savings += chunk * rate
                remaining_contrib_to_account -= chunk
                temp_income -= chunk
                if remaining_contrib_to_account <= 0: break

        data.append({
            "Year": year,
            "Income": round(current_income_sim, 0),
            "Marginal Rate": f"{round(start_marginal_rate * 100, 1)}%",
            "Contribution": round(total_user_contribution, 0),
            "Employer Match": round(match_contribution*0.05, 0),
            "Total Invested": round(total_inflow, 0),
            "Total Room Available": round(total_room_available, 0),
            "RRSP Room Left": round(accumulated_room, 0),
            "Tax Savings": round(tax_savings, 0),
            "Strategy": "Optimized" if extra_contribution > 0 else "Match + Hold"
        })

    return pd.DataFrame(data)

# --- USER INPUTS ---
# Change these values to fit your scenario
df_plan = optimize_rrsp_strategy(
    current_year=2026,
    start_earning_year=2020,         # When you first started working part-time
    current_annual_income=25000,      # Your 2026 income
    full_time_start_year=2030,       # When you graduate/start full-time
    expected_full_time_wage=80000,   # Your expected starting salary
    wage_growth_rate=0.04,           # Expected annual raise (4%)
    retirement_income_target=55000,  # How much income you want in retirement (taxable)
    savings_rate_gross=0.25          # % of gross income you can afford to save (e.g. 0.25 = 25%)
)

print(df_plan.to_string(index=False))
df_plan.to_csv('plan.csv', index=False)