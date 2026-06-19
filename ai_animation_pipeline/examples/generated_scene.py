from manim import *
import numpy as np

class FourierSeriesAnimation(Scene):
    def construct(self):
        # Title and Initial Information
        title = Text("Fourier Series", font_size=48)
        subtitle = Text("Decomposing complex waves into sine waves", font_size=24).next_to(title, DOWN)
        
        self.play(Write(title))
        self.play(FadeIn(subtitle))
        self.wait(1.5)
        self.play(FadeOut(title), FadeOut(subtitle))

        # Setup Coordinate System
        axes = Axes(
            x_range=[0, 10, 1],
            y_range=[-1.5, 1.5, 1],
            axis_config={"color": BLUE, "include_tip": True},
            x_length=10,
            y_length=4
        ).shift(DOWN * 0.5)

        axis_label = Text("Time", font_size=20).next_to(axes.x_axis, RIGHT)
        self.play(Create(axes), Write(axis_label))

        # Logic for square wave approximation: Sum of (4/pi * n) * sin(n * x) for odd n
        harmonics_to_show = [1, 3, 5, 7, 9]
        colors = [YELLOW, ORANGE, RED, PINK, PURPLE]
        
        harmonic_group = VGroup()
        labels_group = VGroup()
        
        # This will hold the visual representation of the sum
        sum_wave = axes.plot(lambda x: 0, color=WHITE)
        current_sum_func = lambda x: 0

        instruction_text = Text("Adding Harmonics:", font_size=28).to_edge(UP).shift(LEFT * 3)
        self.play(Write(instruction_text))

        for i, n in enumerate(harmonics_to_show):
            # Create the individual sine component
            amplitude = 4 / (PI * n)
            harmonic_label = Text("n=" + str(n), font_size=20, color=colors[i])
            harmonic_label.to_edge(UP).shift(RIGHT * (i * 1.2 - 1))

            # Fix scope for lambda
            def make_sine(freq, amp):
                return lambda x: amp * np.sin(freq * x)
            
            sine_func = make_sine(n, amplitude)
            sine_graph = axes.plot(sine_func, color=colors[i], stroke_opacity=0.6)
            
            self.play(
                Create(sine_graph),
                Write(harmonic_label),
                run_time=1
            )

            # Update the sum function
            def make_sum(prev_func, curr_sine):
                return lambda x: prev_func(x) + curr_sine(x)
            
            new_sum_func = make_sum(current_sum_func, sine_func)
            new_sum_wave = axes.plot(new_sum_func, color=WHITE, stroke_width=4)
            
            self.play(
                Transform(sum_wave, new_sum_wave),
                run_time=1.5
            )
            
            current_sum_func = new_sum_func
            harmonic_group.add(sine_graph)
            labels_group.add(harmonic_label)
            self.wait(0.5)

        # Transition to more harmonics
        final_info = Text("More harmonics = Better approximation", font_size=28).to_edge(DOWN)
        self.play(Write(final_info))
        
        # Fade out individual harmonics to show the result clearly
        self.play(harmonic_group.animate.set_stroke(opacity=0.1))
        self.wait(1)

        # Show high-resolution approximation
        def high_res_sum(x):
            return sum([(4 / (PI * k)) * np.sin(k * x) for k in range(1, 100, 2)])
        
        high_res_wave = axes.plot(high_res_sum, color=GREEN, stroke_width=4)
        
        step_text = Text("Using 50 odd harmonics...", font_size=24).next_to(final_info, UP)
        self.play(Write(step_text))
        self.play(Transform(sum_wave, high_res_wave), run_time=3)
        self.wait(2)

        # Cleanup
        self.play(
            FadeOut(harmonic_group),
            FadeOut(labels_group),
            FadeOut(instruction_text),
            FadeOut(final_info),
            FadeOut(step_text)
        )
        
        conclusion = Text("Fourier Series: Any periodic signal can be", font_size=32).shift(UP * 0.5)
        conclusion2 = Text("represented as a sum of sine waves.", font_size=32).next_to(conclusion, DOWN)
        
        self.play(Write(conclusion))
        self.play(Write(conclusion2))
        self.wait(3)