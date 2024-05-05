class Element:
    def __init__(self, tag, data=None, **kwargs):
        self.tag   = tag
        self.data  = data
        self.attrs = { k.replace('_', '-'): v for k, v in kwargs.items() }

    def to_html(self):
        ## Handle data
        data = self.data
        if isinstance(data, list):
            data = "\n".join([x.to_html() for x in data])
        elif isinstance(data, Element):
            data = data.to_html()

        attrs = " " + " ".join([f'{k}="{v}"' for k, v in self.attrs.items()])
        if data is not None:
            return f'<{self.tag}{attrs}>{data}</{self.tag}>'

        return f'<{self.tag}{attrs} />'


class Path(Element):
    def __init__(self, *, x1, y1, x2, y2, width=1, color='black', **kwargs):
        location = f"M{x1},{y1},{x2},{y2}"
        Element.__init__(
            self, 'path', d=location, stroke=color, stroke_width=width, **kwargs,
        )


class Text(Element):
    def __init__(self, text, **kwargs):
        Element.__init__(self, 'text', text, **kwargs)


class TickMark(Path):
    def __init__(self, *, x, y, height, width=1, color='black', **kwargs):
        y2 = y + height
        Path.__init__(self, x1=x, y1=y, x2=x, y2=y2, color=color, width=width)


class LinearGradient(Element):
    def __init__(self, gradient, name=None):
        stops = []
        for i, color in enumerate(gradient.colors):
            offset = round((i + 1)/gradient.size*100, 5)
            stops.append(Element('stop', offset=f"{offset}%", stop_color=color))

        Element.__init__(self, 'lineargradient', stops, id=name)
