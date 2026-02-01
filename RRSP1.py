import pandas as pd

def GetCombinedBrackets():
    fed_brackets = [
        (258482, 0.33),
        (181440, 0.29),
        (117045, 0.26),
        (58523, 0.205),
        (0, 0.14)
    ]
    
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