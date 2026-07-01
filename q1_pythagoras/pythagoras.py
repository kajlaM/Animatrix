from manim import *
import numpy as np

class PythagoreanTheoremProof(Scene):
    def construct(self):
        # --- Constants and Colors ---
        a_len = 3  # Length of leg 'a'
        b_len = 4  # Length of leg 'b'
        c_len = np.sqrt(a_len**2 + b_len**2) # Length of hypotenuse 'c'

        big_square_side = a_len + b_len

        TRIANGLE_COLOR = BLUE_D
        SQUARE_A_COLOR = RED_D
        SQUARE_B_COLOR = GREEN_D
        SQUARE_C_COLOR = YELLOW_D
        OUTER_SQUARE_COLOR = WHITE

        # --- Scene Setup: Two Big Squares ---
        # The first large square (left side)
        outer_square_left = Square(side_length=big_square_side, color=OUTER_SQUARE_COLOR)
        outer_square_left.to_edge(LEFT, buff=1)
        self.play(Create(outer_square_left))
        self.wait(0.5)

        # The second large square (right side)
        outer_square_right = Square(side_length=big_square_side, color=OUTER_SQUARE_COLOR)
        outer_square_right.to_edge(RIGHT, buff=1)
        self.play(Create(outer_square_right))
        self.wait(0.5)

        # --- Arrangement 1: c^2 in the middle ---
        # Triangles for the left square (leaving c^2 in the center)
        # Their right angles point outwards to the corners of the big square.
        # Hypotenuses form the inner square.
        corner_bl_left = outer_square_left.get_corner(DL)

        arr1_t1_pts = [corner_bl_left + a_len * RIGHT, corner_bl_left, corner_bl_left + b_len * UP]
        arr1_t2_pts = [corner_bl_left + big_square_side * RIGHT, corner_bl_left + big_square_side * RIGHT - b_len * RIGHT, corner_bl_left + big_square_side * RIGHT + a_len * UP]
        arr1_t3_pts = [corner_bl_left + big_square_side * RIGHT + big_square_side * UP - a_len * RIGHT, corner_bl_left + big_square_side * RIGHT + big_square_side * UP, corner_bl_left + big_square_side * RIGHT + big_square_side * UP - b_len * UP]
        arr1_t4_pts = [corner_bl_left + big_square_side * UP, corner_bl_left + big_square_side * UP - b_len * UP, corner_bl_left + big_square_side * UP + a_len * RIGHT]

        arr1_t1 = Polygon(*arr1_t1_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        arr1_t2 = Polygon(*arr1_t2_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        arr1_t3 = Polygon(*arr1_t3_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        arr1_t4 = Polygon(*arr1_t4_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        
        triangles_arr1 = VGroup(arr1_t1, arr1_t2, arr1_t3, arr1_t4)
        self.play(Create(triangles_arr1))
        self.wait(1)

        # Highlight the central square (c^2)
        square_c_fill = Square(side_length=c_len, color=SQUARE_C_COLOR, fill_opacity=0.8)
        square_c_fill.move_to(outer_square_left.get_center())
        label_c = Text("c²", color=SQUARE_C_COLOR).next_to(square_c_fill, UP, buff=0.2)
        
        self.play(FadeIn(square_c_fill, scale=0.5))
        self.play(Write(label_c))
        self.wait(1.5)

        # --- Arrangement 2: a^2 + b^2 ---
        # Triangles for the right square (leaving a^2 and b^2)
        # Clone the triangles from the left square to the right square
        triangles_arr2_targets = VGroup(
            arr1_t1.copy(), arr1_t2.copy(), arr1_t3.copy(), arr1_t4.copy()
        )
        
        self.play(
            Transform(triangles_arr1, triangles_arr2_targets.arrange(
                # This arrangement logic should be specific to creating the a^2 + b^2 voids
                # Let's define the target points for the rearrange triangles
                # This specific rearrangement puts a^2 in bottom-left and b^2 in top-right
                # and two a*b rectangles in between.
                # However, a common visual proof keeps the squares of a and b as empty space.
                # So we arrange the four triangles to form two a x b rectangles and two squares.
                # It's usually a large square, with a-square bottom left, b-square top right.
                # And the triangles filling the rest.
            )) # This is not directly usable. Need to define target points.
        )
        self.remove(square_c_fill, label_c)
        self.play(FadeOut(square_c_fill, label_c))
        
        # Define target positions for the four triangles in the right square
        # This rearrangement forms two rectangles of size a x b and leaves two squares of a^2 and b^2
        corner_bl_right = outer_square_right.get_corner(DL)
        
        arr2_t1_target_pts = [corner_bl_right, corner_bl_right + a_len * RIGHT, corner_bl_right + b_len * UP]
        arr2_t2_target_pts = [corner_bl_right + a_len * RIGHT, corner_bl_right + big_square_side * RIGHT, corner_bl_right + a_len * RIGHT + b_len * UP]
        arr2_t3_target_pts = [corner_bl_right + b_len * UP, corner_bl_right + big_square_side * UP, corner_bl_right + a_len * RIGHT + b_len * UP]
        arr2_t4_target_pts = [corner_bl_right + a_len * RIGHT + b_len * UP, corner_bl_right + big_square_side * RIGHT + big_square_side * UP, corner_bl_right + big_square_side * RIGHT + b_len * UP]

        arr2_t1_target = Polygon(*arr2_t1_target_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        arr2_t2_target = Polygon(*arr2_t2_target_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        arr2_t3_target = Polygon(*arr2_t3_target_pts, color=TRIANGLE_COLOR, fill_opacity=0.8)
        arr2_t4_target = Polygon(*arr2_t4_target_pts, color=TRIANGLE_COLOR, fill_opacity=0.8) # This polygon is t4 for arr1 but should be rotated. No, this polygon is arr2_t4_target.

        triangles_arr2_targets = VGroup(arr2_t1_target, arr2_t2_target, arr2_t3_target, arr2_t4_target)
        
        # Transform the triangles from the first arrangement to the second arrangement
        self.play(
            Transform(arr1_t1, arr2_t1_target),
            Transform(arr1_t2, arr2_t2_target),
            Transform(arr1_t3, arr2_t3_target),
            Transform(arr1_t4, arr2_t4_target),
            run_time=2
        )
        self.wait(1)

        # Highlight the two empty squares (a^2 and b^2)
        square_a_fill = Square(side_length=a_len, color=SQUARE_A_COLOR, fill_opacity=0.8)
        square_a_fill.move_to(corner_bl_right + a_len/2 * RIGHT + a_len/2 * UP)
        label_a = Text("a²", color=SQUARE_A_COLOR).next_to(square_a_fill, UP, buff=0.2)

        square_b_fill = Square(side_length=b_len, color=SQUARE_B_COLOR, fill_opacity=0.8)
        square_b_fill.move_to(corner_bl_right + big_square_side*RIGHT + big_square_side*UP - b_len/2*RIGHT - b_len/2*UP)
        label_b = Text("b²", color=SQUARE_B_COLOR).next_to(square_b_fill, UP, buff=0.2)

        self.play(FadeIn(square_a_fill, scale=0.5), FadeIn(square_b_fill, scale=0.5))
        self.play(Write(label_a), Write(label_b))
        self.wait(1.5)

        # --- Conclusion ---
        final_equation = Text("a² + b² = c²", color=WHITE)
        final_equation.to_edge(DOWN, buff=0.5).scale(1.2)
        self.play(Write(final_equation))
        self.wait(2)
        
        # Keep everything on screen for a moment
        self.play(
            outer_square_left.animate.shift(LEFT*2),
            outer_square_right.animate.shift(RIGHT*2),
            triangles_arr1.animate.shift(LEFT*2),
            triangles_arr2_targets.animate.shift(RIGHT*2), # This is where the transformed triangles are.
            square_a_fill.animate.shift(RIGHT*2),
            square_b_fill.animate.shift(RIGHT*2),
            label_a.animate.shift(RIGHT*2),
            label_b.animate.shift(RIGHT*2),
            final_equation.animate.shift(DOWN*2), # Move out of the way for clean final view
            # Move the square_c and label_c back to the original position for a final comparison
            FadeIn(square_c_fill.shift(LEFT*2 + UP*1.5), scale=0.5), # Reposition for final view
            FadeIn(label_c.shift(LEFT*2 + UP*1.5), scale=0.5), # Reposition for final view
            final_equation.animate.scale(0.8).move_to(ORIGIN)
        )
        self.wait(2)
        
        # Final display of the theorem
        self.play(
            FadeOut(outer_square_left, outer_square_right),
            FadeOut(arr1_t1, arr1_t2, arr1_t3, arr1_t4), # These are now in the right square's position.
            FadeOut(square_a_fill, square_b_fill, label_a, label_b, square_c_fill, label_c),
            final_equation.animate.move_to(ORIGIN) # Ensure it's centered
        )
        self.wait(1)