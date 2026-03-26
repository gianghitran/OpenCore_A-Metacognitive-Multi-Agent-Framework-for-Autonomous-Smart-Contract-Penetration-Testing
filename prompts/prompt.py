import dataclasses


@dataclasses.dataclass
class DeepPentestPrompt:

    write_plan: str="""You are an expert smart contract security analyst. Based on the provided smart contract source code, write a comprehensive analysis plan.
    //....
    {...private...}
    //....
    """

    write_RefinePlan: str = """You are an expert smart contract security analyst and Foundry developer. Based on the failed exploit task execution, write a refined plan to fix the exploit code and make it work successfully.
    //....
    {...private...}
    //....
    """

    write_code: str = """"
    {...}
    """

    write_summary: str = """
    {...}

    """
    
    summary_result: str = """
    {...}
    """
    update_plan: str = """
    {...}
    """

    update_RefinePlan: str = """
    {...}
    """
    next_task_details: str = """
    {...}
    """
    check_success: str = """
    {...}
    """

    find_potential_flag: str = """
    {...}
    """

    foundry_output_detection: str = """    
    {...}
    """
        
    static_Report: str = """    
    {...}
    """

