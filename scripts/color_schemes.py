class ColorGradient:
    def __init__(self, colors, max_val, min_val=0, *, scale_fn=None):
        self.colors   = colors
        self.max      = max_val
        self.min      = min_val
        self.range    = self.max - self.min
        self.size     = len(self.colors)
        self.factor = 1
        self.scale_fn = scale_fn or (lambda x: x)
        self.min_scaled = self.scale_fn(self.min) if self.min > 0 else 0
        self.max_scaled = self.scale_fn(self.max*self.factor)
        self.range_scaled    = self.max_scaled - self.min_scaled

    def scale(self, val):
        if val == 0:
            return 0

        return self.scale_fn((val-self.min)*self.factor)

    def percent(self, val):
        if val is None or val < self.min:
            return 0
        elif val > self.max:
            return 100

        return self.scale(val)*100/self.range_scaled

    def pick(self, val):
        if val is None:
            return '#000000'
        elif val < self.min:
            return self.colors[0]
        elif val > self.max:
            return self.colors[-1]

        index = int(max(min(self.scale(val)*self.size//self.range_scaled, self.size - 1), 0))
        return self.colors[index]


## https://gka.github.io/palettes/#/256|d|648fff,785ef0,dc267f|dc267f,fe6100,ffb000|0|1
## #648fff, #785ef0, #dc267f -- #dc267f, #fe6100, #ffb000
BlueRedYellow = [
    '#648fff', '#648eff', '#658eff', '#668dfe', '#668cfe', '#678bfe', '#678bfd', '#688afd',
    '#6889fd', '#6989fc', '#6a88fc', '#6a87fc', '#6b86fb', '#6c86fb', '#6d85fa', '#6d84fa',
    '#6e84fa', '#6f83f9', '#7082f9', '#7181f8', '#7181f8', '#7280f7', '#737ff7', '#747ff6',
    '#757ef6', '#767df5', '#777df5', '#777cf4', '#787bf3', '#797bf3', '#7a7af2', '#7b79f2',
    '#7c78f1', '#7d78f0', '#7e77f0', '#7f76ef', '#8076ee', '#8175ee', '#8274ed', '#8374ec',
    '#8473ec', '#8572eb', '#8671ea', '#8771e9', '#8870e8', '#896fe8', '#8a6fe7', '#8b6ee6',
    '#8c6de5', '#8d6de4', '#8e6ce4', '#8f6be3', '#906ae2', '#916ae1', '#9269e0', '#9368df',
    '#9468de', '#9667dd', '#9766dc', '#9865db', '#9965da', '#9a64d9', '#9b63d8', '#9c63d7',
    '#9d62d6', '#9e61d5', '#9f60d4', '#a060d3', '#a15fd2', '#a25ed1', '#a35dd0', '#a45dcf',
    '#a55cce', '#a65bcd', '#a75acc', '#a85acb', '#a959c9', '#ab58c8', '#ac57c7', '#ad57c6',
    '#ae56c5', '#af55c3', '#b054c2', '#b153c1', '#b253c0', '#b352bf', '#b451bd', '#b550bc',
    '#b64fbb', '#b74fb9', '#b84eb8', '#b94db7', '#ba4cb5', '#bb4bb4', '#bc4ab3', '#bd4ab1',
    '#be49b0', '#bf48af', '#c047ad', '#c146ac', '#c245aa', '#c344a9', '#c443a8', '#c543a6',
    '#c642a5', '#c741a3', '#c840a2', '#c93fa0', '#ca3e9f', '#cb3d9d', '#cb3c9c', '#cc3b9a',
    '#cd3a99', '#ce3997', '#cf3896', '#d03694', '#d13593', '#d23491', '#d3338f', '#d4328e',
    '#d5318c', '#d6308b', '#d72e89', '#d82d87', '#d82c86', '#d92a84', '#da2982', '#db2781',
    '#dd277e', '#dd287c', '#de2a7b', '#df2b79', '#df2c78', '#e02d77', '#e12e75', '#e13074',
    '#e23172', '#e23271', '#e33370', '#e4346f', '#e4356d', '#e5366c', '#e5386b', '#e63969',
    '#e63a68', '#e73b67', '#e73c66', '#e83d64', '#e83e63', '#e93f62', '#e94061', '#ea4260',
    '#ea435e', '#eb445d', '#eb455c', '#ec465b', '#ec475a', '#ed4859', '#ed4958', '#ee4a57',
    '#ee4b55', '#ee4c54', '#ef4d53', '#ef4e52', '#f04f51', '#f05050', '#f0524f', '#f1534e',
    '#f1544d', '#f1554c', '#f2564b', '#f2574a', '#f35849', '#f35948', '#f35a47', '#f45b46',
    '#f45c45', '#f45d44', '#f45e43', '#f55f42', '#f56041', '#f56140', '#f6623f', '#f6633e',
    '#f6643d', '#f7653c', '#f7663b', '#f7683a', '#f76939', '#f86a38', '#f86b37', '#f86c36',
    '#f86d35', '#f96e35', '#f96f34', '#f97033', '#f97132', '#fa7231', '#fa7330', '#fa742f',
    '#fa752e', '#fb762d', '#fb772c', '#fb782b', '#fb792a', '#fb7a29', '#fc7b29', '#fc7c28',
    '#fc7d27', '#fc7f26', '#fc8025', '#fc8124', '#fd8223', '#fd8322', '#fd8421', '#fd8520',
    '#fd861f', '#fd871e', '#fd881d', '#fe891c', '#fe8a1b', '#fe8b1a', '#fe8c19', '#fe8d18',
    '#fe8e17', '#fe8f16', '#fe9015', '#fe9214', '#ff9313', '#ff9412', '#ff9511', '#ff9610',
    '#ff970f', '#ff980e', '#ff990d', '#ff9a0c', '#ff9b0b', '#ff9c0a', '#ff9d09', '#ff9e08',
    '#ffa007', '#ffa106', '#ffa205', '#ffa304', '#ffa403', '#ffa503', '#ffa602', '#ffa702',
    '#ffa801', '#ffa901', '#ffaa00', '#ffac00', '#ffad00', '#ffae00', '#ffaf00', '#ffb000',
]
