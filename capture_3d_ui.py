"""
Capture screenshots of the 3D View UI features via Playwright.
Demonstrates all Phase 1.1 enhancements in the live NiceGUI dashboard.
"""

import time
from playwright.sync_api import sync_playwright

URL = "http://localhost:8766/"
OUTPUT = "output"


def select_option(page, index, option_text):
    """Select a Quasar q-select option by select index and option text.

    index: 0=Network, 1=Color By, etc. (order on the 3D View tab)
    """
    selects = page.locator('.q-select').all()
    selects[index].click()
    page.wait_for_timeout(800)
    # Options are spans inside .q-item__label in the .q-menu
    page.locator(f".q-menu .q-item__label span:text-is('{option_text}')").click()
    page.wait_for_timeout(500)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})

        # ── 1. Load the dashboard ──
        print("Loading dashboard...")
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path=f"{OUTPUT}/ui_01_dashboard_home.png")
        print("  Captured: dashboard home")

        # ── 2. Click the 3D View tab ──
        print("Navigating to 3D View tab...")
        page.locator(".q-tab:has-text('3D View')").click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUTPUT}/ui_02_3d_view_tab.png")
        print("  Captured: 3D View tab (empty)")

        # ── 3. Load & Render with default colors ──
        print("Loading & rendering network...")
        page.locator("button:has-text('Load & Render')").first.click()
        page.wait_for_timeout(4000)
        page.screenshot(path=f"{OUTPUT}/ui_03_network_rendered.png")
        print("  Captured: network rendered in 3D")

        # ── 4. Material color mode ──
        print("Switching to Material color mode...")
        select_option(page, 1, "Material")
        page.locator("button:has-text('Load & Render')").first.click()
        page.wait_for_timeout(4000)
        page.screenshot(path=f"{OUTPUT}/ui_04_material_textures.png")
        print("  Captured: material texture colors")

        # ── 5. Run Analysis + Pressure ──
        print("Running analysis with pressure overlay...")
        select_option(page, 1, "Pressure")
        page.locator("button:has-text('Run Analysis')").first.click()
        page.wait_for_timeout(5000)
        page.screenshot(path=f"{OUTPUT}/ui_05_pressure_overlay.png")
        print("  Captured: pressure color overlay")

        # ── 6. Velocity overlay ──
        print("Switching to velocity overlay...")
        select_option(page, 1, "Velocity")
        page.locator("button:has-text('Run Analysis')").first.click()
        page.wait_for_timeout(5000)
        page.screenshot(path=f"{OUTPUT}/ui_06_velocity_overlay.png")
        print("  Captured: velocity color overlay")

        # ── 7. Flow particles ──
        print("Starting flow particles...")
        page.locator("button:has-text('Start Particles')").click()
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUTPUT}/ui_07_flow_particles.png")
        print("  Captured: flow particles animating")

        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUTPUT}/ui_08_flow_particles_frame2.png")
        print("  Captured: flow particles frame 2")

        # Stop particles
        page.locator("button:has-text('Stop Particles')").click()
        page.wait_for_timeout(500)

        # ── 8. Label toggles ──
        print("Toggling labels...")
        page.locator(".q-checkbox:has-text('Diameters')").click()
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{OUTPUT}/ui_09_labels_diameters.png")
        print("  Captured: diameter labels on")

        page.locator(".q-checkbox:has-text('Flows')").click()
        page.wait_for_timeout(1000)

        page.locator(".q-checkbox:has-text('Pressures')").click()
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{OUTPUT}/ui_10_labels_all.png")
        print("  Captured: all labels on")

        # Turn labels back off for clean views
        page.locator(".q-checkbox:has-text('Diameters')").click()
        page.locator(".q-checkbox:has-text('Flows')").click()
        page.locator(".q-checkbox:has-text('Pressures')").click()
        page.wait_for_timeout(500)

        # ── 9. View presets ──
        print("Testing view presets...")
        page.locator("button:has-text('Plan')").first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUTPUT}/ui_11_plan_view.png")
        print("  Captured: plan view")

        page.locator("button:has-text('Isometric')").click()
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUTPUT}/ui_12_isometric_view.png")
        print("  Captured: isometric view")

        page.locator("button:has-text('Side')").first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUTPUT}/ui_13_side_view.png")
        print("  Captured: side view")

        page.locator("button:has-text('Front')").first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUTPUT}/ui_14_front_view.png")
        print("  Captured: front view")

        # ── 10. EPS Animation ──
        print("Testing EPS animation...")
        # Re-run with pressure to get EPS data
        select_option(page, 1, "Pressure")
        page.locator("button:has-text('Run Analysis')").first.click()
        page.wait_for_timeout(5000)

        # Step forward several times
        step_btn = page.locator("button:has-text('Step Fwd')")
        for _ in range(6):
            step_btn.click()
            page.wait_for_timeout(400)
        page.screenshot(path=f"{OUTPUT}/ui_15_eps_step6.png")
        print("  Captured: EPS at ~T=6h")

        for _ in range(12):
            step_btn.click()
            page.wait_for_timeout(400)
        page.screenshot(path=f"{OUTPUT}/ui_16_eps_step18.png")
        print("  Captured: EPS at ~T=18h")

        # Reset
        page.locator("button:has-text('Reset')").first.click()
        page.wait_for_timeout(500)

        # ── 11. Measure mode ──
        print("Activating measure mode...")
        page.locator("button:has-text('Measure')").first.click()
        page.wait_for_timeout(500)
        page.screenshot(path=f"{OUTPUT}/ui_17_measure_mode.png")
        print("  Captured: measure mode active")
        # Deactivate
        page.locator("button:has-text('Measure')").first.click()
        page.wait_for_timeout(300)

        # ── 12. Full-page final overview ──
        print("Capturing final overview...")
        page.locator("button:has-text('Isometric')").click()
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUTPUT}/ui_18_final_overview.png", full_page=True)
        print("  Captured: full-page overview")

        browser.close()
        print(f"\nDone! 18 screenshots saved to {OUTPUT}/")


if __name__ == "__main__":
    main()
