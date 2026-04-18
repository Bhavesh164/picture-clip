import cProfile
import pstats
import io
import sys

def profile_function(func, *args, **kwargs):
    """
    Standard helper to profile a specific function call.
    Usage: profile_function(my_heavy_task, data)
    """
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args, **kwargs)
    pr.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20) # Top 20 functions
    
    print("\n--- PERFORMANCE REPORT ---")
    print(s.getvalue())
    return result

if __name__ == "__main__":
    print("Performance helper ready. Use me to wrap functions for profiling.")
