import torch
import torch.nn as nn
from src.BaseRNN import BaseRNN, ResidualRNNCell


class ResRNN(BaseRNN):
    def __init__(self, **params):
        super(ResRNN, self).__init__(**params)

        # Create the rnn layers
        self.rnns = nn.ModuleList([])
        self.rnns.append(
            ResidualRNNCell(2, self.hidden_sizes[0], nonlinearity=self.nonlin_hidden)
        )
        for layer in range(1, self.num_rnn_layers):
            self.rnns.append(
                ResidualRNNCell(
                    self.hidden_sizes[layer - 1],
                    self.hidden_sizes[layer],
                    nonlinearity=self.nonlin_hidden,
                )
            )

        self.create_linear_layers()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.to(self.dtype)
        x = x.transpose(0, 1)
        seq_len, batch_size, _ = x.size()

        # h_ts[i].shape = [batch_size, hidden_sizes[i]]
        h_ts = self._init_hidden(batch_size, self.hidden_sizes)

        outputs = []
        # rnn layers
        for t in range(seq_len):
            h_ts[0] = self.rnns[0](x[t], h_ts[0])
            for layer in range(1, self.num_rnn_layers):
                h_ts[layer] = self.rnns[layer](h_ts[layer - 1], h_ts[layer])
            outputs.append(h_ts[-1])

        outputs = torch.stack(outputs)
        outputs = outputs.transpose(0, 1)

        # linear layers
        for layer in range(self.num_lin_layers):
            outputs = self.lins[layer](outputs)
            outputs = self.nonlin_lin(outputs)

        return outputs