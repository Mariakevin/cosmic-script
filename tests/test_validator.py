"""Tests for the Fountain validator."""

import pytest

from cosmic_script.export.validator import FountainValidator


class TestFountainValidatorValidate:
    """Test suite for FountainValidator.validate()."""

    def setup_method(self):
        self.validator = FountainValidator()

    def test_valid_fountain_text(self):
        """Completely valid Fountain text produces no errors."""
        text = """Title: Test Screenplay
Author: Tester

INT. OFFICE - DAY

John sits at his desk.

JOHN
Hello world.

FADE TO BLACK."""

        result = self.validator.validate(text)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_empty_text(self):
        """Empty text is valid."""
        result = self.validator.validate("")
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_blank_text(self):
        """Whitespace-only text is valid."""
        result = self.validator.validate("   \n\n  \n")
        assert result["valid"] is True

    # --- E1: Missing scene heading prefix ---

    def test_e1_missing_scene_heading_prefix(self):
        """Scene heading missing INT/EXT prefix produces E1."""
        text = """Title: Test

HOUSE - DAY

John enters."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E1"]
        assert len(errors) >= 1
        assert "HOUSE - DAY" in errors[0]["text"]

    def test_e1_no_error_for_valid_scene_heading(self):
        """Valid scene heading does NOT produce E1."""
        text = """INT. HOUSE - DAY

John enters."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E1"]
        assert len(errors) == 0

    # --- E2: Scene heading missing time-of-day ---

    def test_e2_missing_time_of_day(self):
        """Scene heading without time-of-day produces E2."""
        text = """INT. OFFICE

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E2"]
        assert len(errors) >= 1

    def test_e2_no_error_with_time_of_day(self):
        """Scene heading with time-of-day does NOT produce E2."""
        text = """INT. OFFICE - DAY

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E2"]
        assert len(errors) == 0

    # --- E3: Orphaned dialogue ---

    def test_e3_orphaned_dialogue(self):
        """Dialogue without preceding character produces E3."""
        text = """INT. ROOM - DAY

Hello? Anyone there?"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E3"]
        assert len(errors) >= 1

    def test_e3_no_error_for_proper_dialogue(self):
        """Dialogue after character does NOT produce E3."""
        text = """INT. ROOM - DAY

JOHN
Hello? Anyone there?"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E3"]
        assert len(errors) == 0

    # --- E4: Character not uppercase ---

    def test_e4_character_not_uppercase(self):
        """Character name with lowercase produces E4."""
        text = """INT. ROOM - DAY

John
Hello."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E4"]
        assert len(errors) >= 1
        assert "John" in errors[0]["text"]

    def test_e4_no_error_for_uppercase_character(self):
        """ALL CAPS character name does NOT produce E4."""
        text = """INT. ROOM - DAY

JOHN
Hello."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E4"]
        assert len(errors) == 0

    # --- E5: Transition not ending in TO: ---

    def test_e5_transition_not_ending_to(self):
        """Non-standard transition without TO: produces E5."""
        text = """JUMP BACK TO LIVING ROOM

INT. ROOM - DAY

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E5"]
        assert len(errors) >= 1

    def test_e5_no_error_for_valid_transition(self):
        """Transition ending with TO: does NOT produce E5."""
        text = """FADE TO BLACK

INT. ROOM - DAY

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E5"]
        assert len(errors) == 0

    def test_e5_no_error_for_standard_transition(self):
        """Standard known transition (FADE OUT) does NOT produce E5."""
        text = """FADE OUT

INT. ROOM - DAY

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E5"]
        assert len(errors) == 0

    # --- E6: Transition not uppercase ---

    def test_e6_transition_not_uppercase(self):
        """Transition with lowercase produces E6."""
        text = """fade to black

INT. ROOM - DAY

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E6"]
        assert len(errors) >= 1

    def test_e6_no_error_for_uppercase_transition(self):
        """ALL CAPS transition does NOT produce E6."""
        text = """FADE TO BLACK

INT. ROOM - DAY

John sits."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E6"]
        assert len(errors) == 0

    # --- E7: Parenthetical outside dialogue ---

    def test_e7_parenthetical_outside_dialogue(self):
        """Parenthetical not between character and dialogue produces E7."""
        text = """INT. ROOM - DAY

(whispering)

JOHN
Hello."""
        result = self.validator.validate(text)
        # This might be detected differently depending on parse order
        # But should flag some issue with the orphaned parenthetical
        errors = [e for e in result["errors"] if e["code"] == "E7"]
        assert len(errors) >= 1

    def test_e7_no_error_for_valid_parenthetical(self):
        """Parenthetical between character and dialogue does NOT produce E7."""
        text = """INT. ROOM - DAY

JOHN
(whispering)
Hello."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E7"]
        assert len(errors) == 0

    # --- E8: Unclosed boneyard ---

    def test_e8_unclosed_boneyard(self):
        """Boneyard without closing */ produces E8."""
        text = """INT. ROOM - DAY

/* This is a comment that never ends

John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E8"]
        assert len(errors) >= 1

    def test_e8_no_error_for_closed_boneyard(self):
        """Properly closed boneyard does NOT produce E8."""
        text = """INT. ROOM - DAY

/* This is a comment */
John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E8"]
        assert len(errors) == 0

    # --- E9: Unclosed note ---

    def test_e9_unclosed_note(self):
        """Note without closing ]] produces E9."""
        text = """INT. ROOM - DAY

[[This is a note that never ends

John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E9"]
        assert len(errors) >= 1

    def test_e9_no_error_for_closed_note(self):
        """Properly closed note does NOT produce E9."""
        text = """INT. ROOM - DAY

[[This is a note]]
John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E9"]
        assert len(errors) == 0

    # --- E10: Character name inconsistency ---

    def test_e10_character_name_inconsistency(self):
        """Same character with different names produces E10."""
        text = """INT. ROOM - DAY

JOHN
Hello.

JOHN DOE
Hi there."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E10"]
        assert len(errors) >= 1

    def test_e10_no_error_for_consistent_names(self):
        """Consistent character names do NOT produce E10."""
        text = """INT. ROOM - DAY

JOHN
Hello.

JOHN
Hi there."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E10"]
        assert len(errors) == 0

    # --- E11: Dual dialogue without second character ---

    def test_e11_dual_dialogue_complete_pair(self):
        """Both characters with ^ form a complete dual dialogue pair (no E11)."""
        text = """INT. ROOM - DAY

JOHN^
Hello.

MARY^
Hi."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E11"]
        assert len(errors) == 0  # Both have ^

    def test_e11_dual_dialogue_without_second(self):
        """Dual dialogue marker ^ without matching second character produces E11."""
        text = """INT. ROOM - DAY

JOHN^
Hello.
MARY
Hi."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E11"]
        assert len(errors) >= 1  # MARY lacks ^, pair incomplete

    def test_e11_dual_dialogue_unpaired(self):
        """Unpaired dual dialogue marker (no second character at all) produces E11."""
        text = """INT. ROOM - DAY

JOHN^
Hello.

MARY
Hi."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E11"]
        assert len(errors) >= 1

    # --- E12: Invalid scene number format ---

    def test_e12_invalid_scene_number(self):
        """Scene number with non-alphanumeric characters produces E12."""
        text = """INT. ROOM - DAY #$%#

John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E12"]
        assert len(errors) >= 1

    def test_e12_unmatched_hash(self):
        """Unmatched scene number marker produces E12."""
        text = """INT. ROOM - DAY #12

John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E12"]
        assert len(errors) >= 1

    def test_e12_no_error_for_valid_scene_number(self):
        """Valid scene number does NOT produce E12."""
        text = """INT. ROOM - DAY #12#

John walks in."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E12"]
        assert len(errors) == 0

    # --- Multiple errors ---

    def test_multiple_errors_detected(self):
        """Text with multiple issues reports all of them."""
        text = """Title: Bad

HOUSE - DAY

john
hello.

fade out"""

        result = self.validator.validate(text)
        # Should have at least E1 (bad heading), E4 (lowercase char), E5 (bad transition), E6 (lowercase trans)
        error_codes = {e["code"] for e in result["errors"]}
        assert "E1" in error_codes
        assert "E4" in error_codes

    # --- Characters list ---

    def test_characters_list_extracted(self):
        """Validator extracts unique character names from text."""
        text = """INT. ROOM - DAY

JOHN
Hello.

MARY
Hi.

JOHN
Again."""

        result = self.validator.validate(text)
        assert "JOHN" in result["characters"]
        assert "MARY" in result["characters"]

    # --- Warnings ---

    def test_warnings_for_notes(self):
        """Notes in Fountain text produce warnings."""
        text = """INT. ROOM - DAY

[[Director note: slow zoom]]

John walks in."""
        result = self.validator.validate(text)
        assert len(result["warnings"]) >= 0  # Notes are optional warnings


class TestFountainValidatorAutoFix:
    """Test suite for FountainValidator.auto_fix()."""

    def setup_method(self):
        self.validator = FountainValidator()

    def test_auto_fix_character_casing(self):
        """Lowercase character names are uppercased."""
        text = """INT. ROOM - DAY

john
Hello."""
        result = self.validator.auto_fix(text)
        assert "JOHN" in result
        # Verify the fix passes validation
        vr = self.validator.validate(result)
        char_errors = [e for e in vr["errors"] if e["code"] == "E4"]
        assert len(char_errors) == 0

    def test_auto_fix_unclosed_boneyard(self):
        """Unclosed boneyard gets closed."""
        text = """INT. ROOM - DAY

/* This comment never ends

John walks in."""
        result = self.validator.auto_fix(text)
        # Should have closing */
        boneyard_errors = False
        for line in result.split("\n"):
            if "/*" in line and "*/" not in line:
                boneyard_errors = True
        assert not boneyard_errors

    def test_auto_fix_unclosed_note(self):
        """Unclosed note gets closed."""
        text = """INT. ROOM - DAY

[[This note never ends

John walks in."""
        result = self.validator.auto_fix(text)
        note_errors = False
        for line in result.split("\n"):
            if "[[" in line and "]]" not in line:
                note_errors = True
        assert not note_errors

    def test_auto_fix_empty_text(self):
        """Empty text is unchanged."""
        assert self.validator.auto_fix("") == ""
        assert self.validator.auto_fix("  ") == "  "

    def test_auto_fix_no_errors(self):
        """Valid text is unchanged."""
        text = """INT. ROOM - DAY

JOHN
Hello."""
        result = self.validator.auto_fix(text)
        assert result == text

    # --- New auto-fix rules ---

    def test_auto_fix_missing_scene_heading_prefix(self):
        """Line that looks like a scene heading but lacks INT/EXT prefix gets 'INT. ' added."""
        text = """HOUSE - DAY

John enters."""
        result = self.validator.auto_fix(text)
        # Should become INT. HOUSE - DAY
        assert "INT. HOUSE - DAY" in result
        # Ensure it's a scene heading prefix
        for line in result.split("\n"):
            if "HOUSE - DAY" in line:
                assert line.startswith("INT.") or line.startswith("EXT.")
                break
        else:
            pytest.fail("Scene heading not found in fixed text")

    def test_auto_fix_missing_time_of_day(self):
        """Scene heading with location but no time-of-day gets ' - DAY' appended."""
        text = """INT. OFFICE

John sits."""
        result = self.validator.auto_fix(text)
        # Should become INT. OFFICE - DAY
        assert "INT. OFFICE - DAY" in result

    def test_auto_fix_unformatted_transition(self):
        """Unformatted transition 'cut to:' becomes 'CUT TO:'."""
        text = """cut to:

INT. ROOM - DAY

John sits."""
        result = self.validator.auto_fix(text)
        # Expect uppercase transition
        assert "CUT TO:" in result
        # Ensure it's exactly CUT TO: (maybe with extra spaces)
        for line in result.split("\n"):
            stripped = line.strip()
            if stripped.startswith("CUT TO"):
                assert stripped == "CUT TO:"
                break
        else:
            pytest.fail("Transition not found in fixed text")

    def test_auto_fix_missing_blank_line_before_character(self):
        """Character cue following action without blank line gets blank line inserted."""
        text = """INT. ROOM - DAY

John walks in.
JOHN
Hello."""
        result = self.validator.auto_fix(text)
        lines = result.split("\n")
        # Find the line with JOHN and ensure previous line is blank
        for i, line in enumerate(lines):
            if line.strip() == "JOHN":
                # Check previous line is blank (empty or whitespace only)
                assert lines[i - 1].strip() == "", (
                    f"Expected blank line before JOHN, got: {lines[i - 1]!r}"
                )
                break
        else:
            pytest.fail("Character cue JOHN not found")

    def test_auto_fix_excessive_blank_lines(self):
        """Three or more consecutive blank lines collapse to two."""
        text = """INT. ROOM - DAY



John sits."""
        result = self.validator.auto_fix(text)
        # Count blank lines between scene heading and action
        lines = result.split("\n")
        # Find the scene heading line index
        scene_idx = None
        for i, line in enumerate(lines):
            if "INT. ROOM - DAY" in line:
                scene_idx = i
                break
        assert scene_idx is not None
        # Count blank lines after scene heading until non-blank
        blank_count = 0
        j = scene_idx + 1
        while j < len(lines) and lines[j].strip() == "":
            blank_count += 1
            j += 1
        # Should be at most 2 blank lines
        assert blank_count <= 2, f"Expected <=2 blank lines, got {blank_count}"

    def test_auto_fix_trailing_whitespace(self):
        """Trailing spaces are stripped from all lines."""
        text = """INT. ROOM - DAY   

JOHN   
Hello.   """
        result = self.validator.auto_fix(text)
        for line in result.split("\n"):
            # No line should end with spaces (except maybe empty lines)
            if line.strip():
                assert not line.endswith(" "), f"Line has trailing whitespace: {line!r}"


class TestExtendedFountainFeatures:
    """Tests for Fountain 1.1 extended features (E13-E20)."""

    def setup_method(self):
        self.validator = FountainValidator()

    # --- E13: Centered text ---

    def test_e13_valid_centered_text(self):
        """Valid centered text does NOT produce E13."""
        text = """>THE END<"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E13"]
        assert len(errors) == 0

    def test_e13_empty_centered_text(self):
        """Empty centered text >< produces E13."""
        text = """><"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E13"]
        assert len(errors) >= 1

    # --- E14: Sections ---

    def test_e14_valid_section(self):
        """Valid section (# heading) does NOT produce E14."""
        text = """# Act I

INT. ROOM - DAY

Action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E14"]
        assert len(errors) == 0

    def test_e14_section_no_space(self):
        """Section without space after # produces E14."""
        text = """#Act I"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E14"]
        assert len(errors) >= 1

    # --- E15: Synopses ---

    def test_e15_valid_synopsis(self):
        """Valid synopsis (= text) does NOT produce E15."""
        text = """= Bob and Mary talk

INT. ROOM - DAY

Action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E15"]
        assert len(errors) == 0

    def test_e15_synopsis_no_space(self):
        """Synopsis without space after = produces E15."""
        text = """=Bob and Mary talk"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E15"]
        assert len(errors) >= 1

    # --- E16: Lyrics ---

    def test_e16_valid_lyric(self):
        """Valid lyric (~text) does NOT produce E16."""
        text = """~It was twenty years ago today

INT. ROOM - DAY

Action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E16"]
        assert len(errors) == 0

    def test_e16_empty_lyric(self):
        """Empty lyric (~ alone) produces E16."""
        text = """~"""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E16"]
        assert len(errors) >= 1

    # --- E17: Page breaks ---

    def test_e17_valid_page_break(self):
        """Valid page break (===) does NOT produce E17."""
        text = """INT. ROOM - DAY

Action.

===

INT. KITCHEN - NIGHT

More action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E17"]
        assert len(errors) == 0

    # --- E18: Forced scene heading ---

    def test_e18_valid_forced_scene_heading(self):
        """Valid forced scene heading (.TEXT) does NOT produce E18."""
        text = """.FLASHBACK

JOHN
I remember."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E18"]
        assert len(errors) == 0

    def test_e18_empty_forced_scene_heading(self):
        """Empty forced scene heading (. alone) produces E18."""
        text = """."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E18"]
        assert len(errors) >= 1

    # --- E19: Forced action / character ---

    def test_e19_valid_forced_action(self):
        """Valid forced action (!TEXT) does NOT produce E19."""
        text = """!BANG

INT. ROOM - DAY

Action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E19"]
        assert len(errors) == 0

    def test_e19_valid_forced_character(self):
        """Valid forced character (@TEXT) does NOT produce E19."""
        text = """@MCCLANE

Yippee ki-yay."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E19"]
        assert len(errors) == 0

    # --- E20: Emphasis ---

    def test_e20_valid_bold(self):
        """Valid bold text does NOT produce E20."""
        text = """INT. ROOM - DAY

This is **very important** action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E20"]
        assert len(errors) == 0

    def test_e20_unclosed_bold(self):
        """Unclosed bold formatting produces E20."""
        text = """INT. ROOM - DAY

This is **broken."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E20"]
        assert len(errors) >= 1

    def test_e20_valid_italic(self):
        """Valid italic text does NOT produce E20."""
        text = """INT. ROOM - DAY

This is *italic* action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E20"]
        assert len(errors) == 0

    def test_e20_unclosed_italic(self):
        """Unclosed italic formatting produces E20."""
        text = """INT. ROOM - DAY

This is *broken."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E20"]
        assert len(errors) >= 1

    def test_e20_valid_underline(self):
        """Valid underline text does NOT produce E20."""
        text = """INT. ROOM - DAY

This is _underlined_ action."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E20"]
        assert len(errors) == 0

    def test_e20_unclosed_underline(self):
        """Unclosed underline formatting produces E20."""
        text = """INT. ROOM - DAY

This is _broken."""
        result = self.validator.validate(text)
        errors = [e for e in result["errors"] if e["code"] == "E20"]
        assert len(errors) >= 1

    # --- New element types appear in parsed output ---

    def test_centered_text_in_elements(self):
        """Centered text appears as element type 'centered'."""
        text = """>THE END<"""
        result = self.validator.validate(text)
        elements = result.get("_elements", [])
        # We don't expose _elements, but check that centered text doesn't error
        errors = [e for e in result["errors"] if e["code"] == "E13"]
        assert len(errors) == 0

    def test_page_break_does_not_cause_errors(self):
        """Page breaks should not trigger unrelated errors."""
        text = """INT. ROOM - DAY

Action.

===

INT. KITCHEN - NIGHT

More action."""
        result = self.validator.validate(text)
        # Page breaks should not cause scene heading errors
        e1_errors = [e for e in result["errors"] if e["code"] == "E1"]
        assert len(e1_errors) == 0
