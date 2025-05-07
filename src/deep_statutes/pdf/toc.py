from typing import Annotated, Optional
from pydantic import BaseModel, Field


class Header(BaseModel):
    type: str
    text: str
    sub_text: str
    page: int  # 1-indexed


# TODO rename to HeaderList or something
class DocumentTOC(BaseModel):
    header_types: list[str]
    headers: list[Header]

    def hierarchy_level(self, header_type: str) -> int:
        """
        Get the hierarchy level of a header type according to the document's order.

        This may not actually be the order in the document since sometimes headers skip levels, but
        it gives us a hint as to how to structure a tree representing the ToC.
        """
        return self.header_types.index(header_type)


class HeaderTreeNode(BaseModel):
    header: Header
    parent: Annotated[Optional["HeaderTreeNode"], Field(exclude=True)] = None
    children: list["HeaderTreeNode"] = []
    page_range: tuple[int, int]  # 1-indexed and inclusive

    def num_pages(self) -> int:
        return self.page_range[1] - self.page_range[0] + 1

    def path(self) -> list["HeaderTreeNode"]:
        """
        Get the path of the header in the tree.
        """
        path = []
        node = self
        while node is not None:
            path.append(node)
            node = node.parent
        path.reverse()
        return path

    @classmethod
    def from_toc(cls, toc: DocumentTOC, num_pages: int) -> "HeaderTreeNode":
        """
        Build a tree of headers from the TOC.
        """
        if toc.headers[0].page == 0:
            # TODO EDF this is a hack to make sure the first header is on page 1
            # should just name everything "page_idx" to make clear it's 0-indexed
            for header in toc.headers:
                header.page += 1

        # TODO EDF not a big deal if this isn't true, but if so it is kind of weird and
        # we need a "doc" level header
        assert toc.headers[0].page == 1, (
            f"First header must be on page 1 but got {toc.headers[0].page}"
        )
        root = HeaderTreeNode(
            header=toc.headers[0], parent=None, page_range=(1, num_pages)
        )
        path: list[HeaderTreeNode] = [root]
        for header in toc.headers[1:]:
            level = toc.hierarchy_level(header.type)
            while toc.hierarchy_level(path[-1].header.type) >= level:
                # this could happen if there isn't a toc entry for "this entire document"
                # we could deal with that if it occurs by always putting in a header at "document" level
                # or something
                assert len(path) > 1

                path[-1].page_range = (path[-1].page_range[0], header.page)
                path.pop()
            node = HeaderTreeNode(
                header=header, parent=path[-1], page_range=[header.page, num_pages]
            )
            path[-1].children.append(node)
            path.append(node)
        return root
