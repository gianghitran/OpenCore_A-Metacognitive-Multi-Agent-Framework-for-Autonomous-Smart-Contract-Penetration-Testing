import re
import json
from server.chat.chat import _chat
from utils.log_common import build_logger
from prompts.prompt import DeepPentestPrompt
from server.chat.chat import _chat
from db.repository.foundryOutput_repository import save_foundry_output

logger = build_logger()


def is_foundry_output(text) -> bool:
    """
    Use LLM to check if the given text is Foundry output.
    Returns True if it's Foundry output, False otherwise.
    """
    
    try:
        # logger.info (f"\nCheck Input:\n{text}\n")
        llm_response, _ = _chat(query=DeepPentestPrompt.foundry_output_detection.format(text=text))
            # llm_respon)
        
        # Clean the response and check for yes/no
        response_clean = llm_response.strip().lower()
        
        # Log the LLM response for debugging
        logger.info(f"LLM foundry detection response: '{llm_response.strip()}'")
        
        # Check if response contains "yes" 
        if "yes" in response_clean:
            return True
        elif "no" in response_clean:
            return False
        else:
            # If unclear response, fallback to keyword detection
            logger.warning(f"Unclear LLM response: '{llm_response}'. Using fallback detection.")
            return _fallback_foundry_detection(text)
            
    except Exception as e:
        logger.error(f"Error in LLM foundry detection: {e}")
        # Fallback to keyword-based detection if LLM fails
        return _fallback_foundry_detection(text)


def _fallback_foundry_detection(text: str) -> bool:
    """
    Fallback method using keyword detection if LLM analysis fails.
    """
    foundry_indicators = [
        # Commands
        "forge test", "forge build", "forge compile", "forge script", "forge create",
        "cast call", "cast send", "cast estimate", "cast block", "cast balance",
        "anvil", "chisel",
        
        # Test results
        "[PASS]", "[FAIL]", "Running 1 test for", "Ran 1 test for", 
        "Test result:", "Suite result:",
        
        # Compilation
        "Compiler run successful", "Contract:", "Solc", "solc",
        
        # Gas and transactions
        "Gas used:", "Gas estimate:", "Transaction hash:",
        
        # Foundry-specific paths and files
        "forge-std/", "lib/forge-std", "/src/", "/test/", "/out/",
        ".t.sol", "ExploitContract", "foundry.toml",
        
        # Cheatcodes
        "vm.prank", "vm.deal", "vm.warp", "vm.roll", "vm.expectRevert",
        "vm.startPrank", "vm.stopPrank"
    ]
    
    text_lower = text.lower()
    found_indicators = [indicator for indicator in foundry_indicators 
                       if indicator.lower() in text_lower]
    
    logger.info(f"Fallback detection found {len(found_indicators)} indicators: {found_indicators[:5]}")
    
    # Consider it Foundry output if at least 2 indicators are found
    return len(found_indicators) >= 2


def check_and_print_foundry_output(session_id, text) -> str:
    """
    Check if text is Foundry output and print 'yes' if it is.
    """
    if not is_foundry_output(text):
        return("no")       
    else:
        save_foundry_output(session_id=session_id, output=text)
        return("yes")


# def main():
#     """
#     Main function for testing - reads input and checks if it's Foundry output.
#     """
#     import sys
    
#     if len(sys.argv) > 1:
#         # Read from command line argument
#         text = " ".join(sys.argv[1:])
#     else:
#         # Read from stdin
#         text = sys.stdin.read()
    
#     check_and_print_foundry_output(text)


# if __name__ == "__main__":
#     main()
