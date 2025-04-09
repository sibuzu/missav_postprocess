            # 若行中只包含空白、數字、.:,--> 這些字元，則跳過
            if all(c in ' 0123456789.:,->-' for c in line):
                continue