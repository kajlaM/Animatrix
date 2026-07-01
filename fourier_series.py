from manim import *
import numpy as np

class FourierSquareWave(Scene):
    # Scene parameters
    X_RANGE = [-PI, 3 * PI]  # X-axis range to display
    Y_RANGE = [-1.5, 1.5]     # Y-axis range to display
    AMPLITUDE = 1             # Amplitude of the square wave
    NUM_TERMS = 15            # Number of odd Fourier terms to sum (e.g., 1, 3, 5, ..., 2*NUM_TERMS - 1)
    GRAPH_RESOLUTION = 200    # Resolution for plotting functions

    def fourier_sum_func(self, x, num_terms_to_sum):
        """Calculates the sum of the first 'num_terms_to_sum' odd Fourier series terms."""
        total_sum = 0
        for k in range(int(num_terms_to_sum)):
            n = 2 * k + 1  # Odd term (1, 3, 5, ...)
            coefficient = (4 * self.AMPLITUDE / PI) * (1 / n)
            total_sum += coefficient * np.sin(n * x)
        return total_sum

    def construct(self):
        # 1. Setup Axes
        axes = Axes(
            x_range=self.X_RANGE,
            y_range=self.Y_RANGE,
            x_length=10,
            y_length=6,
            axis_config={"include_numbers": True, "font_size": 24},
            x_axis_config={
                "numbers_to_include": [-PI, 0, PI, 2 * PI, 3 * PI],
               
            },
            y_axis_config={
                "numbers_to_include": [-self.AMPLITUDE, 0, self.AMPLITUDE],
            }
        ).add_coordinates()
        axes_labels = axes.get_axis_labels(x_label="x", y_label="f(x)")
        self.play(Create(axes), Write(axes_labels))
        self.wait(0.5)

        # 2. Target Square Wave (drawn as segments to handle discontinuities)
        square_wave_segments = VGroup()
        # Iterate through relevant PI multiples in the x_range
        for x_start_segment in np.arange(self.X_RANGE[0] - PI, self.X_RANGE[1] + PI, PI):
            # Calculate amplitude for the current segment (period 2PI, starts at 0 with A)
            # Square wave is A from (2k*PI, (2k+1)*PI) and -A from ((2k+1)*PI, (2k+2)*PI)
            # The sum of sines is A for (0, PI), -A for (PI, 2PI), and 0 at multiples of PI.
            amplitude_for_segment = self.AMPLITUDE
            if int(np.floor(x_start_segment / PI)) % 2 != 0: # If x_start_segment / PI is odd (e.g., -1, 1, 3)
                amplitude_for_segment = -self.AMPLITUDE
            
            # Horizontal segment
            segment_x1 = max(x_start_segment, self.X_RANGE[0])
            segment_x2 = min(x_start_segment + PI, self.X_RANGE[1])
            if segment_x1 < segment_x2:
                square_wave_segments.add(
                    axes.plot_line_graph(
                        [segment_x1, segment_x2], 
                        [amplitude_for_segment, amplitude_for_segment], 
                        stroke_width=2, color=GREY
                    )
                )
            
            # Vertical line at discontinuities (where segments meet)
            # Only draw if the discontinuity point is within the visible x_range
            discontinuity_x = x_start_segment + PI
            if self.X_RANGE[0] < discontinuity_x < self.X_RANGE[1]:
                point_up = axes.coords_to_point(discontinuity_x, self.AMPLITUDE)
                point_down = axes.coords_to_point(discontinuity_x, -self.AMPLITUDE)
                square_wave_segments.add(Line(point_up, point_down, color=GREY, stroke_width=2))

        square_wave_label = Text("Target Square Wave", font_size=24).next_to(axes.get_x_axis().get_right(), RIGHT, buff=0.5).shift(UP*0.5)
        square_wave_label.set_color(GREY)
        self.play(Create(square_wave_segments), Write(square_wave_label))
        self.wait(1)

        # 3. Fourier Series Sum Graph
        self.num_terms_tracker = ValueTracker(0) # Tracks how many odd terms (k) are included in the sum
        
        # This graph continuously updates as self.num_terms_tracker changes
        fourier_sum_graph = always_redraw(
            lambda: axes.plot(
                lambda x: self.fourier_sum_func(x, self.num_terms_tracker.get_value()),
                x_range=self.X_RANGE,
                color=BLUE,
                stroke_width=3,
                resolution=self.GRAPH_RESOLUTION
            )
        )
        
        fourier_sum_label = Text("Fourier Sum", font_size=24).next_to(axes.get_top(), UP, buff=0.2).set_color(BLUE)
        
        self.play(Create(fourier_sum_graph), FadeIn(fourier_sum_label))

        # 4. Display current term count
        term_count_text = Text("Odd Terms: ", font_size=28).to_corner(UL).shift(RIGHT * 0.5)
        term_count_number = always_redraw(
    	lambda: Text(str(int(self.num_terms_tracker.get_value())), font_size=28)
    	.next_to(term_count_text, RIGHT)
	)
        self.play(Write(term_count_text), Write(term_count_number))
        self.wait(1)

        # 5. Loop to add terms one by one
        for k_val in range(self.NUM_TERMS):
            n = 2 * k_val + 1 # The current odd 'n' value (1, 3, 5, ...)
            
            # Function for the individual term being added
            current_term_func = lambda x: (4 * self.AMPLITUDE / PI) * (1 / n) * np.sin(n * x)
            current_term_graph = axes.plot(
                current_term_func,
                x_range=self.X_RANGE,
                color=GREEN,
                stroke_width=2,
                resolution=self.GRAPH_RESOLUTION
            )
            
            # Label for the individual term
            # Adjust label position to be above the max value of the term for better visibility
            # The peak of sin(nx) is at x = PI / (2n), 3PI / (2n), etc.
            label_x_pos = PI / (2 * n) if n > 0 else PI/2 # Prevent division by zero
            term_label = Text(f"Add harmonic n={n}", font_size=20).move_to(
                axes.coords_to_point(label_x_pos, self.AMPLITUDE / n * 1.2)
            ).set_color(GREEN).align_to(fourier_sum_label, LEFT)
            
            # Show the individual term being added
            self.play(Create(current_term_graph), FadeIn(term_label))
            self.wait(0.7)
            
            # Add the term to the sum by updating the tracker value
            self.play(
                self.num_terms_tracker.animate.set_value(k_val + 1), # Increment the count of terms included
                FadeOut(current_term_graph), # The individual term graph fades out as it's incorporated into the sum
                FadeOut(term_label),
                run_time=1.5
            )
            self.wait(0.5)

        # 6. Final state and fade out
        self.wait(2)
        
        self.play(
            FadeOut(axes),
            FadeOut(axes_labels),
            FadeOut(square_wave_segments),
            FadeOut(square_wave_label),
            FadeOut(fourier_sum_graph),
            FadeOut(fourier_sum_label),
            FadeOut(term_count_text),
            FadeOut(term_count_number)
        )
        self.wait(1)