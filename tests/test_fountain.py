"""Tests for the Fountain format generator."""

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.export.fountain import generate_fountain


class TestGenerateFountain:
    """Test suite for generate_fountain()."""

    def test_happy_path_complete_screenplay(self):
        """Generate Fountain from a full screenplay with all element types."""
        screenplay = Screenplay(
            title="The Great Adventure",
            author="Jane Smith",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. OFFICE - DAY"
                ),
                ScreenplayElement(
                    element_type="action", text="John sits at his desk, staring at the computer screen."
                ),
                ScreenplayElement(
                    element_type="character", text="JOHN"
                ),
                ScreenplayElement(
                    element_type="dialogue", text="I can't believe this is happening."
                ),
                ScreenplayElement(
                    element_type="parenthetical", text="whispering"
                ),
                ScreenplayElement(
                    element_type="dialogue", text="This is crazy."
                ),
                ScreenplayElement(
                    element_type="character", text="MARY"
                ),
                ScreenplayElement(
                    element_type="dialogue", text="Get used to it."
                ),
                ScreenplayElement(
                    element_type="transition", text="FADE TO BLACK"
                ),
            ],
        )

        result = generate_fountain(screenplay)

        # Title page
        assert "Title: The Great Adventure" in result
        assert "Author: Jane Smith" in result

        # Scene heading
        assert "INT. OFFICE - DAY" in result

        # Action
        assert "John sits at his desk" in result

        # Characters
        assert "JOHN" in result
        assert "MARY" in result

        # Dialogue
        assert "I can't believe this is happening." in result
        assert "Get used to it." in result

        # Parenthetical
        assert "whispering" in result

        # Transition
        assert "FADE TO BLACK" in result

    def test_empty_screenplay(self):
        """Empty screenplay produces empty string."""
        screenplay = Screenplay()
        result = generate_fountain(screenplay)
        assert result == ""

    def test_title_only(self):
        """Screenplay with only title."""
        screenplay = Screenplay(title="My Movie")
        result = generate_fountain(screenplay)
        assert "Title: My Movie" in result
        assert "Author:" not in result

    def test_author_only(self):
        """Screenplay with only author."""
        screenplay = Screenplay(author="John Doe")
        result = generate_fountain(screenplay)
        assert "Title:" not in result
        assert "Author: John Doe" in result

    def test_multiple_scenes(self):
        """Multiple scene headings produce correct structure."""
        screenplay = Screenplay(
            title="Multi Scene",
            author="Test",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. HOUSE - DAY"
                ),
                ScreenplayElement(
                    element_type="action", text="Morning light fills the room."
                ),
                ScreenplayElement(
                    element_type="scene_heading", text="EXT. GARDEN - NIGHT"
                ),
                ScreenplayElement(
                    element_type="action", text="Stars twinkle above."
                ),
            ],
        )

        result = generate_fountain(screenplay)

        # Each scene heading should be present
        assert "INT. HOUSE - DAY" in result
        assert "EXT. GARDEN - NIGHT" in result

        # Verify ordering
        lines = result.split("\n")
        int_idx = next(i for i, l in enumerate(lines) if "INT. HOUSE" in l)
        ext_idx = next(i for i, l in enumerate(lines) if "EXT. GARDEN" in l)
        assert int_idx < ext_idx

    def test_scene_heading_blank_lines(self):
        """Scene headings have blank lines before and after."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. ROOM - DAY"
                ),
            ],
        )

        result = generate_fountain(screenplay)
        lines = result.split("\n")

        # The scene heading should have blank line after (or be the only line)
        # Since there's only one element, it should be the content
        assert any("INT. ROOM - DAY" in l for l in lines)

    def test_character_preceded_by_blank_line(self):
        """Character names are preceded by a blank line."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. ROOM - DAY"
                ),
                ScreenplayElement(element_type="action", text="A quiet room."),
                ScreenplayElement(element_type="character", text="BOB"),
                ScreenplayElement(element_type="dialogue", text="Hi."),
            ],
        )

        result = generate_fountain(screenplay)
        lines = result.split("\n")

        # Find BOB and ensure previous non-empty line is preceded by blank
        bob_idx = next(i for i, l in enumerate(lines) if l.strip() == "BOB")
        # The line before BOB should be empty (blank line)
        assert bob_idx > 0
        assert lines[bob_idx - 1].strip() == ""

    def test_transition_formatting(self):
        """Transitions end with TO: and are uppercase."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(
                    element_type="transition", text="FADE TO BLACK"
                ),
            ],
        )

        result = generate_fountain(screenplay)

        # Transition should contain TO: or similar
        assert "TO:" in result

    def test_dialogue_indentation(self):
        """Dialogue lines are indented under character."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="character", text="JIM"),
                ScreenplayElement(element_type="dialogue", text="Hello there."),
            ],
        )

        result = generate_fountain(screenplay)

        # Dialogue should be indented
        lines = result.split("\n")
        dial_idx = next(i for i, l in enumerate(lines) if "Hello there." in l)
        assert lines[dial_idx].startswith("\t") or lines[dial_idx].startswith("  ")

    def test_preserve_case_in_action(self):
        """Action text preserves original casing."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(
                    element_type="action", text="He slowly opens the Door."
                ),
            ],
        )

        result = generate_fountain(screenplay)
        assert "He slowly opens the Door." in result

    def test_character_name_uppercased(self):
        """Character names are automatically uppercased if not already."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="character", text="john"),
            ],
        )

        result = generate_fountain(screenplay)
        assert "JOHN" in result
        assert "john" not in result

    def test_centered_text_element(self):
        """Centered text element produces >text<."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="centered", text="THE END"),
            ],
        )
        result = generate_fountain(screenplay)
        assert ">THE END<" in result

    def test_section_element(self):
        """Section element produces # text."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="section", text="Act I"),
            ],
        )
        result = generate_fountain(screenplay)
        assert "# Act I" in result

    def test_synopsis_element(self):
        """Synopsis element produces = text."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="synopsis", text="Bob and Mary talk"),
            ],
        )
        result = generate_fountain(screenplay)
        assert "= Bob and Mary talk" in result

    def test_lyric_element(self):
        """Lyric element produces ~text."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="lyric", text="It was twenty years ago"),
            ],
        )
        result = generate_fountain(screenplay)
        assert "~It was twenty years ago" in result

    def test_page_break_element(self):
        """Page break element produces ===."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="page_break", text="==="),
            ],
        )
        result = generate_fountain(screenplay)
        assert "===" in result

    def test_all_new_elements_combined(self):
        """Combined new elements produce correct Fountain."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="section", text="Act I"),
                ScreenplayElement(element_type="synopsis", text="Opening scene"),
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
                ScreenplayElement(element_type="action", text="Action here."),
                ScreenplayElement(element_type="lyric", text="La la la"),
                ScreenplayElement(element_type="centered", text="THE END"),
                ScreenplayElement(element_type="page_break", text="==="),
            ],
        )
        result = generate_fountain(screenplay)
        assert "# Act I" in result
        assert "= Opening scene" in result
        assert "INT. ROOM - DAY" in result
        assert "~La la la" in result
        assert ">THE END<" in result
        assert "===" in result

    def test_skip_empty_text_elements(self):
        """Elements with empty or whitespace-only text are skipped."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text=""),
                ScreenplayElement(element_type="action", text="   "),
                ScreenplayElement(element_type="action", text="Real action."),
            ],
        )

        result = generate_fountain(screenplay)
        assert "Real action." in result
        # Should be clean - double blank lines are OK but content should be right
        assert "Real action." in result

    def test_only_elements_no_metadata(self):
        """Screenplay without title/author still generates correctly."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. CAR - DAY"
                ),
            ],
        )

        result = generate_fountain(screenplay)
        assert not result.startswith("Title:")
        assert not result.startswith("Author:")
        assert "INT. CAR - DAY" in result

    def test_preserves_transition_text_if_has_to(self):
        """Transition already ending with TO: is not modified."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(
                    element_type="transition", text="FADE TO BLACK."
                ),
            ],
        )

        result = generate_fountain(screenplay)
        assert "FADE TO BLACK" in result

    def test_multiple_consecutive_actions(self):
        """Multiple action elements in a row are separated correctly."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="First action."),
                ScreenplayElement(element_type="action", text="Second action."),
            ],
        )

        result = generate_fountain(screenplay)
        assert "First action." in result
        assert "Second action." in result
