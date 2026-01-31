import pandas as pd

def get_marginal_tax_rate(income):
    """
    Calculates the combined Marginal Tax Rate for a Quebec resident in 2026.
    Includes the 16.5% Quebec Abatement on Federal Tax.
    """
    # 2026 Federal Brackets (Estimated based on 2025 + indexation)
    fed_brackets = [
        (258482, 0.33),
        (181440, 0.29),
        (117045, 0.26),
        (58523, 0.205),
        (0, 0.14) # Changed from 15% to 14% per recent updates
    ]
    
    # 2026 Quebec Brackets (Estimated)
    qc_brackets = [
        (132245, 0.2575),
        (108680, 0.24),
        (54345, 0.19),
        (0, 0.14)
    ]

    # Find Federal Rate
    fed_rate = 0.0
    for threshold, rate in fed_brackets:
        if income > threshold:
            fed_rate = rate
            break
            
    # Find Quebec Rate
    qc_rate = 0.0
    for threshold, rate in qc_brackets:
        if income > threshold:
            qc_rate = rate
            break
    
    # Calculate Combined Rate with Quebec Abatement
    # Formula: (FedRate * (1 - 0.165)) + QcRate
    effective_fed_rate = fed_rate * (1 - 0.165)
    combined_rate = effective_fed_rate + qc_rate
    
    return combined_rate

def optimize_rrsp_strategy(
    current_year=2026,
    start_earning_year=2020,
    current_annual_income=25000,       # e.g., Internship/Part-time
    full_time_start_year=2027,
    expected_full_time_wage=85000,     # Entry level full time
    wage_growth_rate=0.03,             # 3% annual raise
    employer_match_rate=0.05,          # 5% of salary matched
    risk_free_rate=0.05,
    retirement_income_target=60000     # Expected taxable income in retirement
):
    
    # Constants
    rrsp_max_limit_2026 = 33810
    limit_indexing = 0.02 # Assumed annual increase in contribution limit cap
    
    # State variables
    data = []
    accumulated_room = 0.0
    rrsp_balance = 0.0
    
    # Determine retirement tax rate (the benchmark)
    retirement_tax_rate = get_marginal_tax_rate(retirement_income_target)
    
    # Simulation range (e.g., 10 years for planning)
    end_year = full_time_start_year + 10
    
    # 1. Calculate past room (Simulated simply)
    # Assuming minimal usage in past, just accumulating room based on part-time work
    # This is a simplification; normally you'd pull this from CRA MyAccount
    years_worked_before_now = current_year - start_earning_year
    avg_past_income = 15000 # Assumption for student years
    accumulated_room += (avg_past_income * 0.18) * years_worked_before_now

    current_income_sim = current_annual_income

    for year in range(current_year, end_year + 1):
        
        # 1. Update Income
        if year >= full_time_start_year:
            # If it's the first year of full time, switch to that wage
            if year == full_time_start_year:
                current_income_sim = expected_full_time_wage
            else:
                current_income_sim *= (1 + wage_growth_rate)
        
        # 2. Update Contribution Limits
        new_room_generated = current_income_sim * 0.18
        
        # Cap the new room by the annual maximum
        annual_max = rrsp_max_limit_2026 * ((1 + limit_indexing) ** (year - 2026))
        if new_room_generated > annual_max:
            new_room_generated = annual_max
            
        accumulated_room += new_room_generated
        
        # 3. Calculate Marginal Tax Rate
        marginal_rate = get_marginal_tax_rate(current_income_sim)
        
        # 4. Strategy Logic
        
        # A. Employer Match (Always take this)
        match_amount = current_income_sim * employer_match_rate
        # You contribute 5% to get 5%
        user_base_contribution = current_income_sim * employer_match_rate 
        
        # B. Optimization (Should we contribute MORE than the match?)
        # Only contribute extra if your current tax saving > future tax cost
        # and you have the cash flow (assuming you save 20% of gross income total)
        
        extra_contribution = 0.0
        
        if marginal_rate > retirement_tax_rate:
            # Tax arbitrage is positive: Max out RRSP if possible
            # Let's assume you can afford to save up to 18% of your gross income
            max_affordable = (current_income_sim * 0.18)
            remaining_capacity = max_affordable - user_base_contribution
            
            # Use room if available
            extra_contribution = min(remaining_capacity, accumulated_room - user_base_contribution)
            if extra_contribution < 0: extra_contribution = 0

        total_user_contribution = user_base_contribution + extra_contribution
        
        # Check against room limit
        if total_user_contribution > accumulated_room:
            total_user_contribution = accumulated_room
            
        # 5. Update Balances
        accumulated_room -= total_user_contribution
        total_inflow = total_user_contribution + match_amount
        rrsp_balance = (rrsp_balance * (1 + risk_free_rate)) + total_inflow
        
        # 6. Calculate Tax Savings
        # (Simplified: assumes all contributions deducted at marginal rate)
        tax_savings = total_user_contribution * marginal_rate

        data.append({
            "Year": year,
            "Income": round(current_income_sim, 0),
            "Marginal Tax Rate": f"{round(marginal_rate * 100, 1)}%",
            "Rec. Contribution": round(total_user_contribution, 0),
            "Employer Match": round(match_amount*0.05, 0),
            "Total Invested": round(total_inflow, 0),
            "RRSP Room Left": round(accumulated_room, 0),
            "Tax Savings": round(tax_savings, 0),
            "Strategy": "Max Out" if marginal_rate > retirement_tax_rate else "Match Only"
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
    retirement_income_target=55000   # How much income you want in retirement (taxable)
)

print(df_plan.to_string(index=False))