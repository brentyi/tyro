from argparse_color_formatter import ColorHelpFormatter as ColorHelpFormatterBase


class ColorHelpFormatter(ColorHelpFormatterBase):
    def _format_args(self, action, default_metavar):
        """Override _format_args() to ignore nargs and always expect single string
        metavars."""
        get_metavar = self._metavar_formatter(action, default_metavar)
        return get_metavar(1)[0]
