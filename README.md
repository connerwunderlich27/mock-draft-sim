# mock-draft-sim
Mock draft simulator with some fun customizations to make it feel more accurate to your specific league. 

As an avid fantasy football player, I frequently participate in automated mock drafts to familiarize myself with how the real thing may go. However, using apps like Sleeper and ESPN were far too robotic. If I had the 7th pick, I ended up with the same team pretty much every single time. In real drafts, there is much less predictability, particularly deep into the rounds. This personal project uses simulated variance and customizable sliders to make the experience mirror your real league's draft more closely.

This project, my first major project in Python, was a great learning experience. Not only did I learn about certain packages and tools, but I also gained a much deeper understanding of how to structure a real application from scratch. Throughout the process, I picked up skills in object-oriented programming, state management, UI design, and simulation logic, all while making something genuinely fun and useful.

**What I Learned**

Python project architecture: How to break an application into logical modules (draft_engine.py for core logic and app.py for UI), use @dataclass for clean data structures, and design classes that actually model a system (players, teams, and draft state).

**Streamlit development:**
Learned how Streamlit reruns scripts, how session_state preserves state across interactions, how to build reactive UI components, and how to control flow with st.stop(). Also implemented dynamic UI elements like live updating pick displays.

**Game logic & simulation:**
Implemented a full snake-draft algorithm, pick advancement, player pool management, and custom bot behavior. Added controlled additive randomness so bots behave differently each draft, especially in later rounds, making the experience more realistic.

**Data handling with pandas:**
Loaded and validated data from CSVs, transformed fields (like mapping WR-01 into WR), added rookie identification, and built the remaining player pool dynamically as the draft progressed.

**AI decision scoring:**
Designed a scoring system that weighs ADP, positional tendencies, rookie preference, and randomness. Learned how even small tweaks in randomness or score weighting drastically affect draft outcomes.

**User experience thinking:**
Added a dedicated start screen, eliminated unnecessary buttons, implemented an “auto-draft until your pick” mechanic, and introduced a pick-by-pick animation to make the draft feel alive. Learned how clutter builds up quickly and how layout matters.

**Debugging real problems:**
Solved issues with undefined variables, double-click button behavior, Streamlit rerun loops, inconsistent state, and timing delays. Learned to reason about why apps behave unexpectedly when everything reruns on every interaction.

Overall, this project helped me grow from “writing Python scripts” to actually building an application, handling edge cases, architecting features, and thinking critically about how to simulate a realistic draft environment.
