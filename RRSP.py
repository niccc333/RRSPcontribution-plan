import pandas as pd

# ==============================================================================
# SECTION 1: HELPER FUNCTIONS FOR TAX CALCULATIONS
# ==============================================================================
# These functions handle the complexity of Quebec + Federal tax brackets.
# They are used to determine your "Marginal Tax Rate" (tax on next dollar earned).

def get_combined_brackets():
    """
    Returns a sorted list of (threshold, combined_marginal_rate) for 2026.
    
    HOW IT WORKS:
    - Merges Federal and Quebec tax brackets into a unified list.
    - Applies the "Quebec Abatement" (16.5% reduction) to the Federal rate.
    - Returns a list like: [(258k, 53%), (181k, 49%), ...]
    """
    # 2026 Federal Brackets (Estimated based on 2025 + indexation)
    fed_brackets = [
        (258482, 0.33),
        (181440, 0.29),
        (117045, 0.26),
        (58523, 0.205),
        (0, 0.14)
    ]
    
    # 2026 Quebec Brackets (Estimated)
    qc_brackets = [
        (132245, 0.2575),
        (108680, 0.24),
        (54345, 0.19),
        (0, 0.14)
    ]

    # Create a set of all unique thresholds from both governments
    all_thresholds = set(f[0] for f in fed_brackets) | set(q[0] for q in qc_brackets)
    sorted_thresholds = sorted(list(all_thresholds), reverse=True)
    
    combined_brackets = []
    
    for t in sorted_thresholds:
        # Determine Fed Rate strictly at this threshold
        f_rate = 0.0
        for ft, fr in fed_brackets:
            if t >= ft:
                f_rate = fr
                break
                
        # Determine QC Rate strictly at this threshold
        q_rate = 0.0
        for qt, qr in qc_brackets:
            if t >= qt:
                q_rate = qr
                break
        
        # Calculate Combined Rate with Quebec Abatement
        # Formula: (FedRate * (1 - 0.165)) + QcRate
        effective_fed_rate = f_rate * (1 - 0.165)
        combined_rate = effective_fed_rate + q_rate
        
        combined_brackets.append((t, combined_rate))
        
    return combined_brackets

def get_marginal_tax_rate(income, brackets):
    """
    Calculates your marginal rate given your current income.
    Inputs:
        income: Your taxable income
        brackets: The list returned by get_combined_brackets()
    """
    for threshold, rate in brackets:
        if income > threshold:
            return rate
    return brackets[-1][1] # Fallback to lowest rate

# ==============================================================================
# SECTION 2: MAIN OPTIMIZATION SIMULATION
# ==============================================================================
# This is the core engine. It simulates your financial life year-by-year.

def optimize_rrsp_strategy(
    current_year=2026,
    start_earning_year=2020,
    current_annual_income=20000,
    full_time_start_year=2030,
    expected_full_time_wage=80000,
    wage_growth_rate=0.04,
    employer_match_rate=0.05,
    risk_free_rate=0.05,
    retirement_income_target=55000,     # Expected taxable income in retirement
    savings_rate_gross=0.6             # Portion of gross income available for savings
):
    
    # --- A. SETUP & CONSTANTS ---
    rrsp_max_limit_2026 = 33810
    limit_indexing = 0.02 # Assumed annual increase in CRA contribution limits
    
    # Pre-calculate unified tax brackets for use in the loop
    combined_brackets = get_combined_brackets()
    
    # Determine the benchmark: What tax rate will I pay in retirement?
    # If I save tax at 40% now but pay 30% in retirement -> Good Deal.
    # If I save tax at 30% now and pay 30% in retirement -> Neutral (TFSA might be better).
    retirement_tax_rate = get_marginal_tax_rate(retirement_income_target, combined_brackets)
    
    data = []
    accumulated_room = 0.0
    rrsp_balance = 0.0
    
    # Simulation range (10 years after full time starts)
    end_year = full_time_start_year + 10
    
    # --- B. HISTORICAL ROOM CALCULATION ---
    # We estimate how much RRSP room you accumulated while working part-time/internships.
    years_worked_before_now = current_year - start_earning_year
    avg_past_income = 15000 
    accumulated_room += (avg_past_income * 0.18) * years_worked_before_now

    current_income_sim = current_annual_income

    # --- C. MAIN YEARLY LOOP ---
    for year in range(current_year, end_year + 1):
        
        # 1. Update Income (Simulate raises and graduation)
        if year >= full_time_start_year:
            if year == full_time_start_year:
                current_income_sim = expected_full_time_wage
            else:
                current_income_sim *= (1 + wage_growth_rate)
        
        # 2. Update Contribution Limits
        # You earn new room equal to 18% of your previous year's earned income.
        # (Simplified to current year for this simulation)
        new_room_generated = current_income_sim * 0.18
        
        # The government caps new room (e.g. ~$32k)
        annual_max = rrsp_max_limit_2026 * ((1 + limit_indexing) ** (year - 2026))
        if new_room_generated > annual_max:
            new_room_generated = annual_max
            
        # Total Room = Old Room carried forward + New Room
        total_room_available = accumulated_room + new_room_generated
        
        # 3. Strategy Logic (The "Brain")
        
        # STEP 3A: Employer Match
        # ALWAYS take the match. It's free money (100% return instantly).
        match_contribution = current_income_sim * employer_match_rate
        # Your mandatory contribution to get the match:
        user_base_contribution = current_income_sim * employer_match_rate 
        
        # STEP 3B: Optimization (Waterfall Strategy)
        # Should we contribute MORE than the match?
        # Only if our Current Tax Rate > Retirement Tax Rate.
        
        # Calculate how much cash we have available to save
        max_user_cash = (current_income_sim * savings_rate_gross)
        cash_remaining = max_user_cash
        
        # Pay for the mandatory match first using our cash
        cash_remaining -= user_base_contribution
        total_user_contribution = user_base_contribution
        
        # Calculate our "Effective Taxable Income" 
        # (This is Income minus what we've already contributed)
        current_taxable_income = current_income_sim - user_base_contribution
        
        extra_contribution = 0.0
        
        # Loop through tax brackets from Top -> Bottom
        for threshold, rate in combined_brackets:
            # If this bracket's tax rate is NOT higher than retirement rate, stop optimization.
            # It's not worth locking money away if you don't save extra tax.
            if rate <= retirement_tax_rate:
                continue 
            
            # If our income sits in this high bracket...
            if current_taxable_income > threshold:
                # How much income is in this specific bracket?
                income_in_band = current_taxable_income - threshold
                
                # How much CAN we contribute? (Limited by Room and Cash)
                room_remaining = total_room_available - total_user_contribution
                amount_to_contribute = min(income_in_band, room_remaining, cash_remaining)
                
                # Make the contribution
                if amount_to_contribute > 0:
                    extra_contribution += amount_to_contribute
                    total_user_contribution += amount_to_contribute
                    cash_remaining -= amount_to_contribute
                    current_taxable_income -= amount_to_contribute
                
                # Stop if we run out of cash or room
                if cash_remaining <= 0 or (total_room_available - total_user_contribution) <= 0:
                    break
        
        # Final safety check against room limits
        if total_user_contribution > total_room_available:
            total_user_contribution = total_room_available
            
        # 4. Update Balances for next year
        accumulated_room = total_room_available - total_user_contribution
        total_inflow = total_user_contribution + match_contribution
        rrsp_balance = (rrsp_balance * (1 + risk_free_rate)) + total_inflow
        
        # 5. Review Metrics (For display only)
        start_marginal_rate = get_marginal_tax_rate(current_income_sim, combined_brackets)
        
        # Calculate approximate immediate tax savings from this contribution
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
            "Employer Match": round(match_contribution, 0), # Match is "free" money on top
            "Total Invested": round(total_inflow, 0),
            "Total Room Available": round(total_room_available, 0),
            "RRSP Room Left": round(accumulated_room, 0),
            "Tax Savings": round(tax_savings, 0),
            "Strategy": "Optimized" if extra_contribution > 0 else "Match + Hold"
        })

    return pd.DataFrame(data)

if __name__ == "__main__":
    df_plan = optimize_rrsp_strategy()

    print("\n--- RRSP OPTIMIZATION PLAN ---\n")
    print(df_plan.to_string(index=False))
    
    # Save to CSV for Excel/Numbers
    df_plan.to_csv('plan.csv', index=False)
    print("\nPlan saved to 'plan.csv'")